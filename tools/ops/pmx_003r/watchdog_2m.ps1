param(
  [string]$Stamp = "",
  [string]$Root = "C:\projects\NEXT-TRADE",
  [string]$OutDir = "C:\projects\NEXT-TRADE\evidence\pmx003r_auto",
  [int]$NoEntryMinutes = 60,
  [int]$ApiErrStreakKill = 3
)

$ErrorActionPreference = "Stop"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"

# stamp 자동 추론
if ([string]::IsNullOrWhiteSpace($Stamp)) {
  $ev = Join-Path $Root "logs\runtime\profitmax_v1_events.jsonl"
  if (Test-Path $ev) {
    $lastRunStart = Get-Content $ev -Tail 8000 | Select-String -Pattern '"event_type"\s*:\s*"RUN_START"' | Select-Object -Last 1
    if ($lastRunStart) {
      try { $Stamp = ((($lastRunStart.Line) | ConvertFrom-Json).stamp) } catch { }
    }
  }
}
if ([string]::IsNullOrWhiteSpace($Stamp)) { $Stamp = "UNKNOWN_STAMP" }

$dir = Join-Path $OutDir $Stamp
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$evPath = Join-Path $Root "logs\runtime\profitmax_v1_events.jsonl"
if (!(Test-Path $evPath)) { return }

# 최근 30분 타임윈도우 추정: 마지막 20000줄에서 stamp 필터링
$lines = Get-Content $evPath -Tail 20000
$stampLines = @()
foreach ($l in $lines) {
  if ($l -match ('"stamp"\s*:\s*"' + [regex]::Escape($Stamp) + '"')) { $stampLines += $l }
}
if ($stampLines.Count -eq 0) { return }

# api_err_streak_max / ACCOUNT_FAIL / 최근 ENTRY 시각
$apiErrMax = 0
$accountFail = 0
$lastEntryTs = $null
$now = Get-Date

foreach ($l in $stampLines) {
  try {
    $o = $l | ConvertFrom-Json
    if ($o.payload -and $o.payload.api_err_streak -ne $null) {
      $v = [int]$o.payload.api_err_streak
      if ($v -gt $apiErrMax) { $apiErrMax = $v }
    }
    if ($o.event_type -match "ACCOUNT_FAIL|account_check_failed") { $accountFail++ }
    if ($o.event_type -eq "ENTRY") {
      try { $lastEntryTs = [datetime]$o.ts } catch { }
    }
  } catch { }
}

$noEntryTooLong = $false
if ($lastEntryTs) {
  $mins = ($now.ToUniversalTime() - $lastEntryTs.ToUniversalTime()).TotalMinutes
  if ($mins -ge $NoEntryMinutes) { $noEntryTooLong = $true }
}

# KILL RULES: 자동 중단 대신 ALERT + 30분 추출/요약 생성
$trigger = $false
$reason = @()
if ($accountFail -gt 0) { $trigger = $true; $reason += "ACCOUNT_FAIL" }
if ($apiErrMax -gt $ApiErrStreakKill) { $trigger = $true; $reason += "API_ERR_STREAK>$ApiErrStreakKill" }
if ($noEntryTooLong) { $trigger = $true; $reason += "NO_ENTRY_${NoEntryMinutes}m" }

if (-not $trigger) { return }

$reasonStr = ($reason -join "_")
$alertDir = Join-Path $dir ("ALERT_" + $ts + "_" + $reasonStr)
New-Item -ItemType Directory -Force -Path $alertDir | Out-Null

# 1) 최근 윈도우 추출
$extract = Join-Path $alertDir "events_last_window.jsonl"
$stampLines | Out-File -Encoding utf8 $extract

# 2) Python 분석 요약 실행
$py = Join-Path $Root "venv\Scripts\python.exe"
$an = Join-Path $Root "tools\ops\pmx_003r\analyze_jsonl.py"
if (Test-Path $py -and (Test-Path $an)) {
  & $py $an --jsonl $extract --out (Join-Path $alertDir "alert_summary.md") --stamp $Stamp
}

# 3) 알림 텍스트 기록
@"
ALERT_TS=$ts
STAMP=$Stamp
REASON=$reasonStr
API_ERR_MAX=$apiErrMax
ACCOUNT_FAIL_COUNT=$accountFail
LAST_ENTRY_TS=$lastEntryTs
EXTRACT=$extract
"@ | Out-File -Encoding utf8 (Join-Path $alertDir "alert_meta.txt")

Write-Host "ALERT CREATED => $alertDir"

