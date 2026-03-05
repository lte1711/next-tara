param(
    [string]$ApiBase = "http://127.0.0.1:8100"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = "C:\projects\NEXT-TRADE"
$healthPath = Join-Path $projectRoot "evidence\analysis\ph7e_daily_health.txt"

$hardcodedPattern = @'
(?i)(api[_-]?key|secret|token)\s*[:=]\s*['"'][A-Za-z0-9_\-/+=]{16,}['"']
'@
$scanOutput = rg -n --hidden -P "$hardcodedPattern" "$projectRoot" -g "*.py" -g "*.ps1" 2>$null
$secretPass = [string]::IsNullOrWhiteSpace(($scanOutput -join "`n"))

$apiHealthPass = $false
try {
    $h = Invoke-RestMethod -Uri "$ApiBase/api/v1/ops/health" -TimeoutSec 10
    if ($h.status -eq "OK") { $apiHealthPass = $true }
} catch {
    $apiHealthPass = $false
}

$applyDisabledPass = $false
if (Test-Path $healthPath) {
    $txt = Get-Content $healthPath -Raw
    if ($txt -match "ENGINE_APPLY_STATUS=DISABLED") { $applyDisabledPass = $true }
}

$overall = $secretPass -and $apiHealthPass -and $applyDisabledPass

Write-Host "SECRET_SCAN_PASS=$secretPass"
Write-Host "API_HEALTH_PASS=$apiHealthPass"
Write-Host "ENGINE_APPLY_STATUS_DISABLED=$applyDisabledPass"
Write-Host "G0_SMOKE_PASS=$overall"

if (-not $overall) { exit 1 }
exit 0
