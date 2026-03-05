$ErrorActionPreference = "Stop"

$proj = "C:\projects\NEXT-TRADE"
$py = Join-Path $proj "venv\Scripts\python.exe"
$script = Join-Path $proj "tools\ops\evergreen_perf\evg_ha_bb_snapshot.py"

if (-not (Test-Path $py)) { exit 1 }
if (-not (Test-Path $script)) { exit 1 }

& $py $script
exit $LASTEXITCODE

