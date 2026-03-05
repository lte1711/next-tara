$ErrorActionPreference = "Stop"

$repo = "C:\projects\NEXT-TRADE"
$analysis = Join-Path $repo "evidence\analysis"
$logDir = Join-Path $analysis "logs"
$date = Get-Date -Format "yyyyMMdd"
$evidence = Join-Path $analysis ("schtasks_NEXTTRADE_PH7E_FRAMEWORK_DAILY_" + $date + ".txt")

# 1) Capture scheduler verbose info
schtasks /Query /TN "NEXTTRADE_PH7E_FRAMEWORK_DAILY" /V /FO LIST | Out-File $evidence -Encoding utf8

# 2) Parse Last Result
$taskRaw = Get-Content $evidence -Raw
$lastResult = ""
if ($taskRaw -match "Last Result:\s+([0-9\-]+)") {
  $lastResult = $Matches[1]
}

# 3) Parse health file
$healthFile = Join-Path $analysis "ph7e_daily_health.txt"
$health = @{}
if (Test-Path $healthFile) {
  foreach ($line in Get-Content $healthFile) {
    $idx = $line.IndexOf("=")
    if ($idx -gt 0) {
      $k = $line.Substring(0, $idx).Trim()
      $v = $line.Substring($idx + 1).Trim()
      $health[$k] = $v
    }
  }
}

# 4) Find today framework log
$todayLog = Get-ChildItem $logDir -File -Filter ("ph7e_framework_" + $date + ".log") -ErrorAction SilentlyContinue | Select-Object -First 1

$gatePass = ($lastResult -eq "0") -and ($health["STATUS"] -eq "PASS") -and ($health["ENGINE_APPLY_STATUS"] -eq "DISABLED") -and ($null -ne $todayLog)
$gateText = if ($gatePass) { "TRUE" } else { "FALSE" }

"DATE_KST=$(Get-Date)"
"SCHEDULE_LAST_RESULT=$lastResult"
"PH7E_HEALTH_STATUS=$($health["STATUS"])"
"ENGINE_APPLY_STATUS=$($health["ENGINE_APPLY_STATUS"])"
"PH7E_LOG_EXISTS=$([bool]$todayLog)"
"EVIDENCE_SCHTASKS=$evidence"
"EVIDENCE_HEALTH=$healthFile"
"EVIDENCE_LOG=$($todayLog.FullName)"
"PH7E_GATE_E1=$gateText"
