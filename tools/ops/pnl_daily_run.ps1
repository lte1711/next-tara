param(
  [string]$ApiBase = "http://127.0.0.1:8100",
  [int]$Limit = 200,
  [int]$MaxPages = 50,
  [int]$SleepMs = 120
)

$ErrorActionPreference = "Stop"

$root = "C:\projects\NEXT-TRADE"
$ev = Join-Path $root "evidence\pnl"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
New-Item -ItemType Directory -Force -Path $ev | Out-Null

$fillsPath = Join-Path $ev ("fills_raw_" + $ts + ".json")
$reportJson = Join-Path $ev ("pnl_report_" + $ts + ".json")
$reportTxt  = Join-Path $ev ("pnl_report_" + $ts + ".txt")

Write-Host "=== STEP 1: Fetch fills from API ==="
$tz = [System.TimeZoneInfo]::FindSystemTimeZoneById("Korea Standard Time")
$nowUtc = [DateTimeOffset]::UtcNow
$nowKst = [System.TimeZoneInfo]::ConvertTime($nowUtc, $tz)
$midnightKst = [DateTimeOffset]::new($nowKst.Year, $nowKst.Month, $nowKst.Day, 0, 0, 0, $nowKst.Offset)
$fromTs = [int64]$midnightKst.ToUnixTimeMilliseconds()

$runStartMs = $null
try {
  $health = Invoke-RestMethod -Uri "$ApiBase/api/v1/ops/health" -TimeoutSec 10
  $enginePid = [int]($health.data.engine_pid)
  if ($enginePid -gt 0) {
    $proc = Get-Process -Id $enginePid -ErrorAction Stop
    $runStartMs = [int64]([DateTimeOffset]$proc.StartTime).ToUnixTimeMilliseconds()
    if ($runStartMs -lt $fromTs) { $fromTs = $runStartMs }
  }
} catch {
  $runStartMs = $null
}

$cursor = $null
$all = @()
for($i = 1; $i -le $MaxPages; $i++){
  $url = "$ApiBase/api/v1/trading/fills?limit=$Limit&from_ts=$fromTs"
  if($cursor){ $url += "&cursor=$cursor" }
  Write-Host "GET $url"
  $resp = Invoke-RestMethod -Uri $url -TimeoutSec 20
  if(-not $resp.items -or $resp.items.Count -eq 0){ break }
  $all += $resp.items
  if((-not $resp.has_more) -or (-not $resp.next_cursor)){ break }
  $cursor = [int64]$resp.next_cursor
  Start-Sleep -Milliseconds $SleepMs
}

$uniq = @{}
foreach($it in $all){
  $k = ""
  if($it.trade_id){ $k = "tid:$($it.trade_id)" }
  elseif($it.order_id -and $it.ts){ $k = "oid:$($it.order_id)_ts:$($it.ts)" }
  else { $k = "ts:$($it.ts)_p:$($it.price)_q:$($it.qty)_s:$($it.side)" }
  $uniq[$k] = $it
}
$items = @($uniq.Values)
@{ items = $items } | ConvertTo-Json -Depth 30 | Out-File -Encoding utf8 $fillsPath
Write-Host "Saved: $fillsPath"

Write-Host "=== STEP 2: Compute PnL (KST midnight + total) ==="
$py = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$calc = Join-Path $root "tools\ops\pnl_daily_from_fills.py"
if ($runStartMs) {
  & $py $calc $fillsPath --out $reportJson --run-start-ms $runStartMs 2>&1 | Tee-Object -FilePath $reportTxt
} else {
  & $py $calc $fillsPath --out $reportJson 2>&1 | Tee-Object -FilePath $reportTxt
}

Write-Host "Saved: $reportJson"
Write-Host "Saved: $reportTxt"
Write-Host "=== DONE ==="
