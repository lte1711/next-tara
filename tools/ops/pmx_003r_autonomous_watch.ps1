param(
  [string]$Stamp = "",
  [int]$DurationMinutes = 1440,
  [int]$IntervalMinutes = 10,
  [double]$PnlLimit = -1.5
)

$ErrorActionPreference = "Stop"

Set-Location "C:\projects\NEXT-TRADE"

$py = "C:\projects\NEXT-TRADE\venv\Scripts\python.exe"
$events = "C:\projects\NEXT-TRADE\logs\runtime\profitmax_v1_events.jsonl"

if (-not $Stamp -or $Stamp.Trim() -eq "") {
  try {
    $json = & $py tools\ops\pmx_003r_metrics.py --events $events
    $obj = $json | ConvertFrom-Json
    $Stamp = [string]$obj.stamp
  } catch {
    throw "Failed to auto-detect stamp. Pass -Stamp explicitly."
  }
}

$start = Get-Date
$runDir = "C:\projects\NEXT-TRADE\evidence\pmx\003r_autonomous\$Stamp"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

"[START] $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K') stamp=$Stamp duration_min=$DurationMinutes interval_min=$IntervalMinutes" |
  Tee-Object -FilePath (Join-Path $runDir "watchdog.log") -Append

function Stop-Runner {
  $targets = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -match "profitmax_v1_runner" }
  foreach ($t in $targets) {
    try { Stop-Process -Id $t.ProcessId -Force -ErrorAction SilentlyContinue } catch {}
  }
}

function Save-Last30MinEvents {
  param([string]$OutPath, [string]$TargetStamp)
  $cut = (Get-Date).ToUniversalTime().AddMinutes(-30)
  $lines = Get-Content $events
  $buf = New-Object System.Collections.Generic.List[string]
  foreach ($ln in $lines) {
    if ([string]::IsNullOrWhiteSpace($ln)) { continue }
    try { $o = $ln | ConvertFrom-Json } catch { continue }
    if (($o.stamp -ne $TargetStamp)) { continue }
    $ts = [datetimeoffset]::Parse([string]$o.ts).UtcDateTime
    if ($ts -ge $cut) { [void]$buf.Add($ln) }
  }
  $buf | Set-Content -Encoding UTF8 $OutPath
}

$elapsed = 0
while ($elapsed -lt $DurationMinutes) {
  $ts = Get-Date -Format "yyyyMMdd_HHmmss"
  $jsonOut = Join-Path $runDir "snapshot_$ts.json"
  $txtOut = Join-Path $runDir "snapshot_$ts.txt"

  $raw = & $py tools\ops\pmx_003r_metrics.py --events $events --stamp $Stamp --pnl-limit $PnlLimit --json-out $jsonOut --text-out $txtOut
  $obj = $raw | ConvertFrom-Json

  $line = "[SNAPSHOT] $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K') " +
          "EXIT=$($obj.exit_total) TP=$($obj.tp) SL=$($obj.sl) PnL=$($obj.session_realized_pnl) " +
          "BLOCKED=$($obj.strategy_blocked) ACCOUNT_FAIL=$($obj.account_fail) API_ERR=$($obj.api_err_streak_max) " +
          "KILL=$($obj.kill_now)"
  $line | Tee-Object -FilePath (Join-Path $runDir "watchdog.log") -Append

  if ($obj.kill_now -eq $true) {
    "[KILL] Triggered at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')" |
      Tee-Object -FilePath (Join-Path $runDir "watchdog.log") -Append
    Stop-Runner

    $incidentDir = Join-Path $runDir ("incident_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
    New-Item -ItemType Directory -Force -Path $incidentDir | Out-Null
    Save-Last30MinEvents -OutPath (Join-Path $incidentDir "events_last30m.jsonl") -TargetStamp $Stamp
    Copy-Item $jsonOut (Join-Path $incidentDir "trigger_metrics.json") -Force
    Copy-Item $txtOut (Join-Path $incidentDir "trigger_metrics.txt") -Force

    "[INCIDENT] saved=$incidentDir" | Tee-Object -FilePath (Join-Path $runDir "watchdog.log") -Append
    break
  }

  Start-Sleep -Seconds ($IntervalMinutes * 60)
  $elapsed = [int]((Get-Date) - $start).TotalMinutes
}

# final report
$finalJson = Join-Path $runDir "final_report.json"
$finalTxt  = Join-Path $runDir "final_report.txt"
& $py tools\ops\pmx_003r_metrics.py --events $events --stamp $Stamp --pnl-limit $PnlLimit --json-out $finalJson --text-out $finalTxt | Out-Null

"[END] $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K') final_json=$finalJson final_txt=$finalTxt" |
  Tee-Object -FilePath (Join-Path $runDir "watchdog.log") -Append

