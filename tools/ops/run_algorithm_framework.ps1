$ErrorActionPreference = "Stop"

$root = "C:\projects\NEXT-TRADE"
$py = Join-Path $root "venv\Scripts\python.exe"
if (!(Test-Path $py)) {
  $py = "python"
}

Push-Location $root
try {
  $env:PYTHONPATH = Join-Path $root "src"
  & $py -m next_trade.algorithm.evidence_miner_v2
  & $py -m next_trade.algorithm.implant_queue
  & $py -m next_trade.algorithm.framework_health
} finally {
  Pop-Location
}
