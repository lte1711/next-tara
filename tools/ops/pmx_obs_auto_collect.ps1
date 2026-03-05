param(
  [switch]$StartOnly,
  [switch]$Mid15m,
  [switch]$End60m,
  [int]$MidDelaySec = (15 * 60),
  [int]$EndDelaySec = (45 * 60)
)

$root = "C:\projects\NEXT-TRADE"
$ev = Join-Path $root "evidence\pmx"
$eventsFile = Join-Path $root "logs\runtime\profitmax_v1_events.jsonl"
$engineVerifyLog = Join-Path $root "logs\runtime\engine_verify.out.log"
# Avoid saturated baseline windows; overridable via env.
$ordersLimit = 50
if ($env:PMX_ORDERS_LIMIT) {
  try {
    $ordersLimit = [int]$env:PMX_ORDERS_LIMIT
    if ($ordersLimit -lt 1) { $ordersLimit = 50 }
    if ($ordersLimit -gt 200) { $ordersLimit = 200 }
  } catch {
    $ordersLimit = 50
  }
}
New-Item -ItemType Directory -Force -Path $ev | Out-Null

$stamp = if ($env:PMX_STAMP) { $env:PMX_STAMP } else { Get-Date -Format "yyyyMMdd_HHmmss" }
$start = Join-Path $ev ("session_start_" + $stamp + ".txt")
$mid = Join-Path $ev ("session_mid_15m_" + $stamp + ".txt")
$end = Join-Path $ev ("session_end_60m_" + $stamp + ".txt")
$mix = Join-Path $ev ("runtime_mix_gate_" + $stamp + ".txt")

function Invoke-Json([string]$url) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 15
    $raw = [string]$r.Content
    $obj = $null
    try { $obj = $raw | ConvertFrom-Json } catch { $obj = $null }
    return @{
      ok = $true
      status = [int]$r.StatusCode
      raw = $raw
      obj = $obj
      reason = ""
    }
  } catch {
    return @{
      ok = $false
      status = $null
      raw = ""
      obj = $null
      reason = $_.Exception.Message
    }
  }
}

function Get-EventCursor() {
  if (!(Test-Path $eventsFile)) {
    return @{
      total = $null
      last_ts = $null
      reason = "events_file_missing"
    }
  }

  try {
    $lines = Get-Content $eventsFile
    $total = $lines.Count
    $lastTs = $null
    if ($total -gt 0) {
      try {
        $last = $lines[$total - 1] | ConvertFrom-Json
        if ($last.PSObject.Properties["ts"]) { $lastTs = [string]$last.ts }
      } catch {
        $lastTs = $null
      }
    }
    return @{
      total = $total
      last_ts = $lastTs
      reason = ""
    }
  } catch {
    return @{
      total = $null
      last_ts = $null
      reason = $_.Exception.Message
    }
  }
}

function Get-OrdersCount($ordersObj) {
  if ($null -eq $ordersObj) { return $null }
  if ($ordersObj.PSObject.Properties["count"] -and $ordersObj.count -is [int]) { return [int]$ordersObj.count }
  if ($ordersObj.PSObject.Properties["items"] -and $ordersObj.items -is [System.Collections.IEnumerable]) {
    try { return @($ordersObj.items).Count } catch { return $null }
  }
  return $null
}

function Get-MaxTsFromItems($obj) {
  if ($null -eq $obj) { return $null }
  if (!($obj.PSObject.Properties["items"]) -or !($obj.items -is [System.Collections.IEnumerable])) { return $null }
  $maxTs = $null
  foreach ($it in @($obj.items)) {
    try {
      if ($it -and $it.PSObject.Properties["ts"]) {
        $ts = [int64]$it.ts
        if ($null -eq $maxTs -or $ts -gt $maxTs) { $maxTs = $ts }
      }
    } catch {}
  }
  return $maxTs
}

function Get-OrderStatusCounts($ordersObj) {
  if ($null -eq $ordersObj) {
    return @{
      open_orders_count = $null
      canceled_count = $null
      rejected_count = $null
      reason = "orders_payload_missing"
    }
  }
  if (!($ordersObj.PSObject.Properties["items"]) -or !($ordersObj.items -is [System.Collections.IEnumerable])) {
    return @{
      open_orders_count = $null
      canceled_count = $null
      rejected_count = $null
      reason = "orders_items_missing"
    }
  }

  $open = 0
  $canceled = 0
  $rejected = 0
  foreach ($it in @($ordersObj.items)) {
    try {
      $st = ""
      if ($it.PSObject.Properties["status"]) { $st = ([string]$it.status).ToUpperInvariant() }
      switch ($st) {
        "NEW" { $open++ }
        "PARTIALLY_FILLED" { $open++ }
        "CANCELED" { $canceled++ }
        "REJECTED" { $rejected++ }
      }
    } catch {}
  }
  return @{
    open_orders_count = $open
    canceled_count = $canceled
    rejected_count = $rejected
    reason = ""
  }
}

function Get-FillsCount($statusObj) {
  if ($null -eq $statusObj) { return $null }
  if ($statusObj.PSObject.Properties["summary"] -and $statusObj.summary) {
    $s = $statusObj.summary
    if ($s.PSObject.Properties["fills"] -and $s.fills -is [int]) { return [int]$s.fills }
    if ($s.PSObject.Properties["fills_count"] -and $s.fills_count -is [int]) { return [int]$s.fills_count }
  }
  return 0
}

function Get-BlockedCount($statusObj) {
  if ($null -eq $statusObj) { return $null }
  $count = 0
  if ($statusObj.PSObject.Properties["events"] -and $statusObj.events) {
    foreach ($e in @($statusObj.events)) {
      try {
        $etype = ""
        if ($e.PSObject.Properties["event_type"]) { $etype = [string]$e.event_type }
        if ($etype -eq "STRATEGY_BLOCKED") { $count++ ; continue }
        if ($e.PSObject.Properties["payload"] -and $e.payload) {
          $action = ""
          if ($e.payload.PSObject.Properties["action"]) { $action = [string]$e.payload.action }
          if ($action -match "blocked") { $count++ }
        }
      } catch {}
    }
    return $count
  }
  return 0
}

function Get-S001Blocked($statusObj) {
  if ($null -eq $statusObj) { return $null }
  $count = 0
  if ($statusObj.PSObject.Properties["events"] -and $statusObj.events) {
    foreach ($e in @($statusObj.events)) {
      try {
        $code = ""
        $action = ""
        if ($e.PSObject.Properties["payload"] -and $e.payload) {
          if ($e.payload.PSObject.Properties["code"]) { $code = [string]$e.payload.code }
          if ($e.payload.PSObject.Properties["action"]) { $action = [string]$e.payload.action }
        }
        if ($code -eq "S001" -and $action -match "blocked") { $count++ }
      } catch {}
    }
    return $count
  }
  return 0
}

function Write-ScalarOrNull([string]$name, $value, [string]$reason, [string]$path) {
  if ($null -eq $value) {
    "$name=null" | Out-File -Append -Encoding utf8 $path
    if ($reason) { "${name}_reason=$reason" | Out-File -Append -Encoding utf8 $path }
  } else {
    "$name=$value" | Out-File -Append -Encoding utf8 $path
  }
}

function Get-HaFilterCounts() {
  if (!(Test-Path $engineVerifyLog)) {
    return @{
      ha_filter_eval_count = $null
      ha_filter_pass_count = $null
      ha_filter_skip_count = $null
      ha_filter_log_path = $engineVerifyLog
      ha_filter_tail_lines = $null
      reason = "engine_verify_log_missing"
    }
  }

  try {
    $tailLimit = 2000
    if ($env:PMX_ENGINE_TAIL_LINES) {
      try {
        $tailLimit = [int]$env:PMX_ENGINE_TAIL_LINES
        if ($tailLimit -lt 100) { $tailLimit = 100 }
        if ($tailLimit -gt 50000) { $tailLimit = 50000 }
      } catch {
        $tailLimit = 2000
      }
    }

    $lines = Get-Content $engineVerifyLog -Tail $tailLimit -ErrorAction SilentlyContinue
    $tailLines = @($lines).Count
    # Use SimpleMatch-based counting to avoid regex edge cases and encoding issues.
    $haLines = @($lines | Select-String -SimpleMatch "[LiveS2B][HA_FILTER]")
    $enabledLines = @($haLines | Select-String -SimpleMatch "enabled=1")
    $passLines = @($enabledLines | Select-String -SimpleMatch "ha_ok=True")
    $skipLines = @($enabledLines | Select-String -SimpleMatch "ha_ok=False")

    $evalCount = $enabledLines.Count
    $passCount = $passLines.Count
    $skipCount = $skipLines.Count

    if ($evalCount -eq 0) {
      return @{
        ha_filter_eval_count = $null
        ha_filter_pass_count = $null
        ha_filter_skip_count = $null
        ha_filter_log_path = $engineVerifyLog
        ha_filter_tail_lines = $tailLines
        reason = "ha_filter_log_not_found"
      }
    }
    return @{
      ha_filter_eval_count = $evalCount
      ha_filter_pass_count = $passCount
      ha_filter_skip_count = $skipCount
      ha_filter_log_path = $engineVerifyLog
      ha_filter_tail_lines = $tailLines
      reason = ""
    }
  } catch {
    return @{
      ha_filter_eval_count = $null
      ha_filter_pass_count = $null
      ha_filter_skip_count = $null
      ha_filter_log_path = $engineVerifyLog
      ha_filter_tail_lines = $null
      reason = $_.Exception.Message
    }
  }
}

function Snap($path, $label) {
  "=== $label $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File -Encoding utf8 $path

  $ops = Invoke-Json "http://127.0.0.1:8100/api/v1/ops/health"
  $status = Invoke-Json "http://127.0.0.1:8100/api/profitmax/status"
  $orders = Invoke-Json ("http://127.0.0.1:8100/api/v1/trading/orders?limit=" + $ordersLimit)
  $fillsApi = Invoke-Json ("http://127.0.0.1:8100/api/v1/trading/fills?limit=" + $ordersLimit)
  $pnl = Invoke-Json "http://127.0.0.1:8100/api/v1/ledger/pnl"
  $cursor = Get-EventCursor
  $haCounts = Get-HaFilterCounts

  if ($ops.ok) { $ops.raw | Out-File -Append -Encoding utf8 $path } else { "ops_health=ERR $($ops.reason)" | Out-File -Append -Encoding utf8 $path }
  if ($status.ok) { $status.raw | Out-File -Append -Encoding utf8 $path } else { "profitmax_status=ERR $($status.reason)" | Out-File -Append -Encoding utf8 $path }
  if ($orders.ok) { $orders.raw | Out-File -Append -Encoding utf8 $path } else { "orders=ERR $($orders.reason)" | Out-File -Append -Encoding utf8 $path }
  if ($fillsApi.ok) { $fillsApi.raw | Out-File -Append -Encoding utf8 $path } else { "fills_api=ERR $($fillsApi.reason)" | Out-File -Append -Encoding utf8 $path }
  if ($pnl.ok) { $pnl.raw | Out-File -Append -Encoding utf8 $path } else { "pnl=ERR $($pnl.reason)" | Out-File -Append -Encoding utf8 $path }

  "=== PMX V1.2 NORMALIZED ===" | Out-File -Append -Encoding utf8 $path
  $ordersCount = if ($orders.ok) { Get-OrdersCount $orders.obj } else { $null }
  $statusCounts = if ($orders.ok) { Get-OrderStatusCounts $orders.obj } else { @{
      open_orders_count = $null
      canceled_count = $null
      rejected_count = $null
      reason = $orders.reason
    }
  }
  $fillsCount = if ($fillsApi.ok) {
      Get-OrdersCount $fillsApi.obj
    } elseif ($status.ok) {
      Get-FillsCount $status.obj
    } else { $null }
  $blockedCount = if ($status.ok) { Get-BlockedCount $status.obj } else { $null }
  $s001Blocked = if ($status.ok) { Get-S001Blocked $status.obj } else { $null }
  $maxOrderTs = if ($orders.ok) { Get-MaxTsFromItems $orders.obj } else { $null }
  $maxFillTs = if ($fillsApi.ok) { Get-MaxTsFromItems $fillsApi.obj } else { $null }
  # EV in v1.2: cumulative events-file cursor count.
  $evTotal = $cursor.total

  Write-ScalarOrNull "orders_count" $ordersCount $(if ($orders.ok) { "orders_count_not_found_in_payload" } else { $orders.reason }) $path
  Write-ScalarOrNull "open_orders_count" $statusCounts.open_orders_count $(if ($statusCounts.reason) { $statusCounts.reason } else { "open_orders_count_not_found" }) $path
  Write-ScalarOrNull "canceled_count" $statusCounts.canceled_count $(if ($statusCounts.reason) { $statusCounts.reason } else { "canceled_count_not_found" }) $path
  Write-ScalarOrNull "rejected_count" $statusCounts.rejected_count $(if ($statusCounts.reason) { $statusCounts.reason } else { "rejected_count_not_found" }) $path
  Write-ScalarOrNull "fills_count" $fillsCount $(if ($status.ok) { "fills_count_not_found_in_status" } else { $status.reason }) $path
  Write-ScalarOrNull "max_order_ts" $maxOrderTs $(if ($orders.ok) { "max_order_ts_not_found" } else { $orders.reason }) $path
  Write-ScalarOrNull "max_fill_ts" $maxFillTs $(if ($fillsApi.ok) { "max_fill_ts_not_found" } else { $fillsApi.reason }) $path
  Write-ScalarOrNull "blocked_count" $blockedCount $(if ($status.ok) { "blocked_count_not_found_in_events" } else { $status.reason }) $path
  Write-ScalarOrNull "s001_blocked" $s001Blocked $(if ($status.ok) { "s001_counter_not_found_in_events" } else { $status.reason }) $path
  Write-ScalarOrNull "ev" $evTotal $(if ($cursor.reason) { $cursor.reason } else { "ev_cursor_not_available" }) $path
  Write-ScalarOrNull "events_total" $evTotal $(if ($cursor.reason) { $cursor.reason } else { "events_total_not_available" }) $path
  Write-ScalarOrNull "event_last_ts" $cursor.last_ts $(if ($cursor.reason) { $cursor.reason } else { "event_last_ts_not_available" }) $path
  Write-ScalarOrNull "ha_filter_eval_count" $haCounts.ha_filter_eval_count $(if ($haCounts.reason) { $haCounts.reason } else { "ha_filter_eval_count_not_found" }) $path
  Write-ScalarOrNull "ha_filter_pass_count" $haCounts.ha_filter_pass_count $(if ($haCounts.reason) { $haCounts.reason } else { "ha_filter_pass_count_not_found" }) $path
  Write-ScalarOrNull "ha_filter_skip_count" $haCounts.ha_filter_skip_count $(if ($haCounts.reason) { $haCounts.reason } else { "ha_filter_skip_count_not_found" }) $path
  Write-ScalarOrNull "ha_filter_tail_lines" $haCounts.ha_filter_tail_lines "ha_filter_tail_not_available" $path
  if ($haCounts.ha_filter_log_path) { "ha_filter_log_path=$($haCounts.ha_filter_log_path)" | Out-File -Append -Encoding utf8 $path }
}

"=== runtime_mix_v2 gate $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File -Encoding utf8 $mix
powershell -NoProfile -ExecutionPolicy Bypass -File "$root\tools\ops\verify_runtime_mix_v2.ps1" *>> $mix

# Start snapshot (v1.2 required baseline)
Snap $start "PMX START SNAPSHOT"

if ($StartOnly) {
  "OK: wrote $start" | Write-Host
  "OK: wrote $mix" | Write-Host
  exit 0
}

if ($Mid15m) {
  Snap $mid "PMX MID 15m SNAPSHOT"
  "OK: wrote $start" | Write-Host
  "OK: wrote $mid" | Write-Host
  "OK: wrote $mix" | Write-Host
  exit 0
}

if ($End60m) {
  Snap $end "PMX END 60m SNAPSHOT"
  "OK: wrote $start" | Write-Host
  "OK: wrote $end" | Write-Host
  "OK: wrote $mix" | Write-Host
  exit 0
}

Start-Sleep -Seconds $MidDelaySec
Snap $mid "PMX MID 15m SNAPSHOT"

Start-Sleep -Seconds $EndDelaySec
Snap $end "PMX END 60m SNAPSHOT"

"OK: wrote $start" | Write-Host
"OK: wrote $mid" | Write-Host
"OK: wrote $end" | Write-Host
"OK: wrote $mix" | Write-Host
