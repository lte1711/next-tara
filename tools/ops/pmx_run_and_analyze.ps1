param(
  [switch]$StartOnly,
  [string]$ProjectRoot = "C:\projects\NEXT-TRADE"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$opsDir = Join-Path $ProjectRoot "tools\ops"
$evDir = Join-Path $ProjectRoot "evidence\pmx"
$collector = Join-Path $opsDir "pmx_obs_auto_collect.ps1"
$analyzer = Join-Path $opsDir "pmx_session_analyzer_v1.py"
$venvPy = Join-Path $ProjectRoot "venv\Scripts\python.exe"

if (!(Test-Path $collector)) { throw "collector not found: $collector" }
if (!(Test-Path $analyzer)) { throw "analyzer not found: $analyzer" }
if (!(Test-Path $venvPy)) { throw "venv python not found: $venvPy" }
New-Item -ItemType Directory -Force -Path $evDir | Out-Null

Write-Host "[RUN] collector"
if ($StartOnly) {
  powershell -NoProfile -ExecutionPolicy Bypass -File $collector -StartOnly
} else {
  powershell -NoProfile -ExecutionPolicy Bypass -File $collector
}
if ($LASTEXITCODE -ne 0) { throw "collector failed with code $LASTEXITCODE" }

# Collect latest stamp from newest start file.
$start = Get-ChildItem $evDir -File -Filter "session_start_*.txt" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1
if ($null -eq $start) { throw "start snapshot not found" }

$stamp = [System.Text.RegularExpressions.Regex]::Match($start.Name, "session_start_(.+)\.txt").Groups[1].Value
if ([string]::IsNullOrWhiteSpace($stamp)) { throw "failed to parse stamp from $($start.Name)" }
Write-Host "[STAMP] $stamp"

if ($StartOnly) {
  Write-Host "[SKIP] StartOnly mode: analyzer not executed"
  exit 0
}

$mid = Join-Path $evDir ("session_mid_15m_" + $stamp + ".txt")
$end = Join-Path $evDir ("session_end_60m_" + $stamp + ".txt")
if (!(Test-Path $mid)) { throw "mid snapshot missing: $mid" }
if (!(Test-Path $end)) { throw "end snapshot missing: $end" }

$report = Join-Path $evDir ("analysis_" + $stamp + ".json")
$summary = Join-Path $evDir ("analysis_" + $stamp + "_summary.txt")
Write-Host "[RUN] analyzer"
& $venvPy $analyzer $start.FullName $mid $end --summary-out $summary | Out-File -Encoding utf8 $report
if ($LASTEXITCODE -ne 0) { throw "analyzer failed with code $LASTEXITCODE" }

Write-Host "[OK] report=$report"
Write-Host "[OK] summary=$summary"
