param(
    [switch]$NoStart
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = "C:\projects\NEXT-TRADE"
$uiRoot = "C:\projects\NEXT-TRADE-UI"
$apiScript = Join-Path $projectRoot "tools\honey_reports\start_api_8100.ps1"
$uiScript = Join-Path $uiRoot "scripts\start-dev.ps1"

function Stop-PortProcess {
    param([int]$Port)
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        try {
            Stop-Process -Id $listener.OwningProcess -Force -ErrorAction Stop
        } catch {
            # ignore
        }
    }
}

# Standard policy: use only 8100(API) + 3001(UI), terminate old 3000/3001/8100 listeners first.
Stop-PortProcess -Port 3000
Stop-PortProcess -Port 3001
Stop-PortProcess -Port 8100
Start-Sleep -Seconds 2

if ($NoStart) {
    Write-Host "STOP_ONLY=OK"
    exit 0
}

& powershell -ExecutionPolicy Bypass -File $apiScript -Port 8100 -KillExisting
Start-Sleep -Seconds 2
$apiReady = Get-NetTCPConnection -State Listen -LocalPort 8100 -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $apiReady) {
    throw "API start failed: port 8100 is not listening"
}

Start-Process -FilePath "powershell" -ArgumentList @(
    "-ExecutionPolicy", "Bypass",
    "-File", $uiScript
) -WorkingDirectory $uiRoot -WindowStyle Hidden | Out-Null

Start-Sleep -Seconds 3
$ports = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 3000,3001,8100 } | Select-Object LocalAddress,LocalPort,OwningProcess,State | Sort-Object LocalPort
$ports | Format-Table -AutoSize
