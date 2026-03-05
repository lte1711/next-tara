param(
  [string]$Root = "C:\projects\NEXT-TRADE",
  [string]$RunStamp = "",
  [int]$DryMinutes = 15
)

$ErrorActionPreference = "Stop"
Set-Location $Root

$events = Join-Path $Root "logs\runtime\profitmax_v1_events.jsonl"
$outBase = Join-Path $Root "evidence\pmx003r_auto"
$py = Join-Path $Root "venv\Scripts\python.exe"

if (!(Test-Path $events)) {
  throw "events file not found: $events"
}

if ([string]::IsNullOrWhiteSpace($RunStamp)) {
  $lastRunStart = Get-Content $events -Tail 10000 | Select-String -Pattern '"event_type"\s*:\s*"RUN_START"' | Select-Object -Last 1
  if ($lastRunStart) {
    try {
      $RunStamp = (($lastRunStart.Line | ConvertFrom-Json).stamp)
    } catch {}
  }
}
if ([string]::IsNullOrWhiteSpace($RunStamp)) {
  throw "RunStamp auto-detection failed. Pass -RunStamp explicitly."
}

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$dryStamp = "PMX003R_DRY_HA015_$ts"
$evd = Join-Path $outBase $dryStamp
New-Item -ItemType Directory -Force -Path $evd | Out-Null

Write-Host "[STEP A] 24H 종료 증거 확인"
$runEnd = Get-Content $events -Tail 20000 | Select-String -Pattern ('"stamp"\s*:\s*"' + [regex]::Escape($RunStamp) + '".*"event_type"\s*:\s*"RUN_END"') | Select-Object -Last 1
$watchDir = Join-Path $outBase $RunStamp
$watchSnap = if (Test-Path $watchDir) { Get-ChildItem $watchDir -File -Filter "snap_*.txt" | Sort-Object LastWriteTime -Descending | Select-Object -First 1 } else { $null }
$finalReport = Join-Path $watchDir "FINAL_REPORT.md"

@"
RUN_STAMP=$RunStamp
RUN_END_FOUND=$([bool]$runEnd)
RUN_END_LINE=$($runEnd.Line)
WATCH_SNAPSHOT_LAST=$($watchSnap.FullName)
WATCH_SNAPSHOT_TS=$($watchSnap.LastWriteTime)
FINAL_REPORT_EXISTS=$(Test-Path $finalReport)
FINAL_REPORT_PATH=$finalReport
"@ | Out-File -Encoding utf8 (Join-Path $evd "stepA_evidence.txt")

Write-Host "[STEP B] DRY 15분 기동 (015 관측 모드)"
$env:NEXT_TRADE_HA_GATE_ENABLE = "0"
$env:NEXT_TRADE_HA_GATE_MODE = "OBSERVE_ONLY"
$env:NEXT_TRADE_MAX_CONSECUTIVE_SL = "2"
$env:NEXT_TRADE_VOL_ENTRY_ENABLE = "1"
$env:NEXT_TRADE_HA_HIGHER_TF = "15m"
$env:NEXT_TRADE_HA_ENTRY_TF = "5m"
$env:PMX_STAMP = $dryStamp

$stdout = Join-Path $evd "dry_stdout.log"
$stderr = Join-Path $evd "dry_stderr.log"
$hours = [double]$DryMinutes / 60.0

& $py "archive_legacy\ops_scripts\profitmax_v1_runner.py" --dry-run --session-hours $hours --loop-sec 5 1> $stdout 2> $stderr

Write-Host "[STEP C] Gate HA-2 증거 추출"
$stampLines = Get-Content $events -Tail 20000 | Select-String -Pattern ('"stamp"\s*:\s*"' + [regex]::Escape($dryStamp) + '"') | ForEach-Object { $_.Line }
$stampPath = Join-Path $evd "events_$dryStamp.jsonl"
$stampLines | Out-File -Encoding utf8 $stampPath

$runStartLine = $stampLines | Select-String -Pattern '"event_type"\s*:\s*"RUN_START"' | Select-Object -First 1
$entryLine = $stampLines | Select-String -Pattern '"event_type"\s*:\s*"ENTRY"' | Select-Object -First 1
$blockedLine = $stampLines | Select-String -Pattern '"event_type"\s*:\s*"STRATEGY_BLOCKED"' | Select-Object -First 1

@"
DRY_STAMP=$dryStamp
RUN_START_PRESENT=$([bool]$runStartLine)
RUN_START_LINE=$($runStartLine.Line)
ENTRY_PRESENT=$([bool]$entryLine)
ENTRY_LINE=$($entryLine.Line)
BLOCKED_PRESENT=$([bool]$blockedLine)
BLOCKED_LINE=$($blockedLine.Line)
"@ | Out-File -Encoding utf8 (Join-Path $evd "gate_ha2_evidence.txt")

Write-Host "DONE => $evd"
Write-Host "Submit files:"
Write-Host " - $(Join-Path $evd 'stepA_evidence.txt')"
Write-Host " - $(Join-Path $evd 'gate_ha2_evidence.txt')"
Write-Host " - $stdout"
