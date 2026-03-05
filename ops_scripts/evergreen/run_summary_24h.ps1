$ErrorActionPreference = "SilentlyContinue"

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$root = "C:\projects\NEXT-TRADE\evidence\evergreen"
$outPath = Join-Path $root "run_summary_$ts.txt"
$tmpPath = "$outPath.tmp"
$lockPath = Join-Path $root ".lock_run_summary_24h"

if (Test-Path $lockPath) {
  exit 0
}
New-Item -ItemType File -Path $lockPath -Force | Out-Null

try {
  $files = Get-ChildItem $root -File -Filter "session_60m_*.txt" -ErrorAction SilentlyContinue

  $entry = 0
  $exit = 0
  $tp = 0
  $sl = 0
  $blocked = 0

  foreach ($f in $files) {
    $c = Get-Content $f.FullName
    $entryVal = ($c | Select-String "^ENTRY=" | ForEach-Object { ($_ -split "=")[1] } | Select-Object -First 1)
    $exitVal = ($c | Select-String "^EXIT=" | ForEach-Object { ($_ -split "=")[1] } | Select-Object -First 1)
    $tpVal = ($c | Select-String "^TP=" | ForEach-Object { ($_ -split "=")[1] } | Select-Object -First 1)
    $slVal = ($c | Select-String "^SL=" | ForEach-Object { ($_ -split "=")[1] } | Select-Object -First 1)
    $blockedVal = ($c | Select-String "^BLOCKED=" | ForEach-Object { ($_ -split "=")[1] } | Select-Object -First 1)

    $entry += [int]($(if ($entryVal) { $entryVal } else { 0 }))
    $exit += [int]($(if ($exitVal) { $exitVal } else { 0 }))
    $tp += [int]($(if ($tpVal) { $tpVal } else { 0 }))
    $sl += [int]($(if ($slVal) { $slVal } else { 0 }))
    $blocked += [int]($(if ($blockedVal) { $blockedVal } else { 0 }))
  }

  $out = @()
  $out += "STAMP=RUN24H_$ts"
  $out += "ENTRY_TOTAL=$entry"
  $out += "EXIT_TOTAL=$exit"
  $out += "TP_TOTAL=$tp"
  $out += "SL_TOTAL=$sl"
  $out += "BLOCKED_TOTAL=$blocked"
  $out += "SESSION_FILE_COUNT=$($files.Count)"

  $out | Out-File -Encoding utf8 $tmpPath
  Move-Item -Force $tmpPath $outPath
} finally {
  Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
}
