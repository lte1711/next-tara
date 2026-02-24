# SR72 Evidence Collector (NEXT-TRADE)
# - Collect API health, logs endpoints, local metrics files, and basic port/process snapshots.
# - DOES NOT stop/restart anything. Read-only.

param(
  [int]$Hours = 24,
  [int]$Limit = 200,
  [string]$OutRoot = "C:\projects\NEXT-TRADE\evidence\phase-shadowrun",
  [string]$BackendBase = "http://127.0.0.1:8000",
  [string]$UiBase = "http://127.0.0.1:3001"
)

$ErrorActionPreference = "Continue"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = Join-Path $OutRoot ("SR72_{0}" -f $ts)

$dirs = @(
  $outDir,
  (Join-Path $outDir "logs"),
  (Join-Path $outDir "metrics"),
  (Join-Path $outDir "snapshots"),
  (Join-Path $outDir "api")
)

foreach ($d in $dirs) { New-Item -ItemType Directory -Force -Path $d | Out-Null }

function Write-File($path, $content) {
  $content | Out-File -FilePath $path -Encoding utf8
}

function Curl-Text($url) {
  try {
    return (Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 10).Content
  } catch {
    return ("ERROR: {0}`nURL: {1}" -f $_.Exception.Message, $url)
  }
}

function Curl-Status($url) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 10
    return $r.StatusCode
  } catch {
    try {
      return $_.Exception.Response.StatusCode.value__
    } catch {
      return -1
    }
  }
}

# 0) meta
$meta = @()
$meta += "SR72 Evidence Collector"
$meta += "ts=$ts"
$meta += "host=$env:COMPUTERNAME"
$meta += "user=$env:USERNAME"
$meta += "backend=$BackendBase"
$meta += "ui=$UiBase"
$meta += "hours=$Hours"
$meta += "limit=$Limit"
Write-File (Join-Path $outDir "notes.md") ($meta -join "`n")

# 1) Port snapshots
$net8000 = (netstat -ano | Select-String ":8000")
$net3001 = (netstat -ano | Select-String ":3001")
Write-File (Join-Path $outDir "snapshots\netstat_8000.txt") ($net8000 | ForEach-Object { $_.Line })
Write-File (Join-Path $outDir "snapshots\netstat_3001.txt") ($net3001 | ForEach-Object { $_.Line })

# 2) Process snapshots (best-effort)
try {
  $py = Get-Process python -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,StartTime
  $node = Get-Process node -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,StartTime
  $next = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match "node|next|python" } | Select-Object Id,ProcessName,StartTime
  Write-File (Join-Path $outDir "snapshots\proc_python.txt") ($py | Format-Table | Out-String)
  Write-File (Join-Path $outDir "snapshots\proc_node.txt") ($node | Format-Table | Out-String)
  Write-File (Join-Path $outDir "snapshots\proc_all_filtered.txt") ($next | Format-Table | Out-String)
} catch {
  Write-File (Join-Path $outDir "snapshots\proc_error.txt") $_.Exception.Message
}

# 3) Backend API status codes
$apiChecks = @(
  @{ name="ops_health"; url="$BackendBase/api/ops/health" },
  @{ name="ops_evergreen_status"; url="$BackendBase/api/ops/evergreen/status" },
  @{ name="ops_history"; url="$BackendBase/api/ops/history?hours=$Hours" },
  @{ name="ops_alerts"; url="$BackendBase/api/ops/alerts" },
  @{ name="ops_logs_stdout"; url="$BackendBase/api/ops/logs/stdout?limit=$Limit" },
  @{ name="ops_logs_stderr"; url="$BackendBase/api/ops/logs/stderr?limit=$Limit" },
  @{ name="state_engine"; url="$BackendBase/api/state/engine" },
  @{ name="state_positions"; url="$BackendBase/api/state/positions" },
  @{ name="history_risks"; url="$BackendBase/api/history/risks?limit=20" }
)

$statusLines = @()
foreach ($c in $apiChecks) {
  $code = Curl-Status $c.url
  $statusLines += ("{0}={1} {2}" -f $c.name, $code, $c.url)

  # Also save response body (small) for the important ones
  if ($c.name -in @("ops_health","ops_evergreen_status","state_engine","state_positions","history_risks")) {
    $body = Curl-Text $c.url
    Write-File (Join-Path $outDir ("api\{0}.json" -f $c.name)) $body
  }
}
Write-File (Join-Path $outDir "api\status_codes.txt") ($statusLines -join "`n")

# 4) UI proxy quick check (health/status)
$uiChecks = @(
  @{ name="ui_ops_health"; url="$UiBase/api/ops/health" },
  @{ name="ui_ops_evergreen_status"; url="$UiBase/api/ops/evergreen/status" }
)
$uiStatus = @()
foreach ($c in $uiChecks) {
  $code = Curl-Status $c.url
  $uiStatus += ("{0}={1} {2}" -f $c.name, $code, $c.url)
}
Write-File (Join-Path $outDir "api\ui_status_codes.txt") ($uiStatus -join "`n")

# 5) Metrics copy (best-effort)
$metricCandidates = @(
  "C:\projects\NEXT-TRADE\metrics\evergreen_metrics.jsonl",
  "C:\projects\NEXT-TRADE\metrics\live_obs.jsonl"
)
foreach ($m in $metricCandidates) {
  if (Test-Path $m) {
    Copy-Item -Force $m (Join-Path $outDir "metrics") -ErrorAction SilentlyContinue
  }
}

# 6) Optional: tail logs if known paths exist (best-effort)
$logCandidates = @(
  "C:\projects\NEXT-TRADE\logs\*.log",
  "C:\projects\NEXT-TRADE\logs\*.err",
  "C:\projects\NEXT-TRADE\logs\*.out"
)
foreach ($p in $logCandidates) {
  Get-ChildItem $p -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 10 |
    ForEach-Object {
      $dest = Join-Path $outDir "logs"
      Copy-Item -Force $_.FullName $dest -ErrorAction SilentlyContinue
    }
}

# 7) Final summary
$summary = @()
$summary += "DONE: $outDir"
$summary += "Backend status:"
$summary += (Get-Content (Join-Path $outDir "api\status_codes.txt") -ErrorAction SilentlyContinue)
$summary += ""
$summary += "UI status:"
$summary += (Get-Content (Join-Path $outDir "api\ui_status_codes.txt") -ErrorAction SilentlyContinue)
Write-File (Join-Path $outDir "SUMMARY.txt") ($summary -join "`n")

Write-Host ""
Write-Host "SR72 evidence collected -> $outDir"
Write-Host "Key files:"
Write-Host " - SUMMARY.txt"
Write-Host " - api\status_codes.txt"
Write-Host " - metrics\ (if present)"
Write-Host ""
