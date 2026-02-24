# C:\projects\NEXT-TRADE\tools\runbooks\start_backend.ps1
param(
	[switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host "=== NEXT-TRADE BACKEND START (8000) ==="

$root = "C:\projects\NEXT-TRADE"
Set-Location $root

# PYTHONPATH 고정
$env:PYTHONPATH = "C:\projects\NEXT-TRADE\src;C:\projects\NEXT-TRADE"

# 포트 점유 확인
Write-Host "Checking port 8000..."
$existing = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existing) {
	$existingPid = $existing.OwningProcess
	if (-not $Force) {
		Write-Host "Port 8000 already in use (PID=$existingPid). Skipping start. Use -Force to restart."
		return
	}
	Write-Host "Port 8000 in use (PID=$existingPid). Stopping..."
	Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
	Start-Sleep -Seconds 1
}

Write-Host "Starting uvicorn ops_web.app:app on 127.0.0.1:8000 ..."
& "$root\venv\Scripts\python.exe" -m uvicorn ops_web.app:app --host 127.0.0.1 --port 8000 --log-level info
