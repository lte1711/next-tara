$ErrorActionPreference = "SilentlyContinue"

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$outPath = "C:\projects\NEXT-TRADE\evidence\evergreen\session_60m_$ts.txt"
$tmpPath = "$outPath.tmp"
$lockPath = "C:\projects\NEXT-TRADE\evidence\evergreen\.lock_report_60m"

if (Test-Path $lockPath) {
  exit 0
}
New-Item -ItemType File -Path $lockPath -Force | Out-Null

try {
  $logCandidates = @(
    "C:\projects\NEXT-TRADE\logs\runtime\engine_stdout.log",
    "C:\projects\NEXT-TRADE\logs\runtime\engine_supervisor.log",
    "C:\projects\NEXT-TRADE\logs\runtime\profitmax_v1_events.jsonl"
  )

  $logPath = $null
  foreach ($p in $logCandidates) {
    if (Test-Path $p) { $logPath = $p; break }
  }

  $log = @()
  if ($logPath) {
    $log = Get-Content $logPath -Tail 500
  }

  $entry = ($log | Select-String "ENTRY").Count
  $exit = ($log | Select-String "EXIT").Count
  $tp = ($log | Select-String "TP").Count
  $sl = ($log | Select-String "SL").Count
  $blocked = ($log | Select-String "BLOCKED").Count

  $out = @()
  $out += "STAMP=SESSION60M_$ts"
  $out += "LOG_SOURCE=$logPath"
  $out += "ENTRY=$entry"
  $out += "EXIT=$exit"
  $out += "TP=$tp"
  $out += "SL=$sl"
  $out += "BLOCKED=$blocked"

  $out | Out-File -Encoding utf8 $tmpPath
  Move-Item -Force $tmpPath $outPath
} finally {
  Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
}
