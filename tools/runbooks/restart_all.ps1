# C:\projects\NEXT-TRADE\tools\runbooks\restart_all.ps1
param(
	[switch]$Force
)

$ErrorActionPreference = "Continue"

Write-Host "=== RESTART ALL (8000/3001) ==="

Write-Host "[1] Show ports..."
netstat -ano | findstr ":8000"
netstat -ano | findstr ":3001"

Write-Host ""
Write-Host "[2] Start backend..."
if ($Force) {
	powershell -NoProfile -ExecutionPolicy Bypass -File C:\projects\NEXT-TRADE\tools\runbooks\start_backend.ps1 -Force
} else {
	powershell -NoProfile -ExecutionPolicy Bypass -File C:\projects\NEXT-TRADE\tools\runbooks\start_backend.ps1
}

Write-Host "[3] Start UI..."
if ($Force) {
	powershell -NoProfile -ExecutionPolicy Bypass -File C:\projects\NEXT-TRADE\tools\runbooks\start_ui.ps1 -Force
} else {
	powershell -NoProfile -ExecutionPolicy Bypass -File C:\projects\NEXT-TRADE\tools\runbooks\start_ui.ps1
}
