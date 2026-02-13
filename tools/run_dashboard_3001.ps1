Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ROOT = "C:\projects\NEXT-TRADE-UI"  # 필요시 경로 수정
Set-Location $ROOT

# Never use 3000
$env:PORT = "3001"
Write-Host "[DASHBOARD] Starting on :3001 (never 3000) ..." -ForegroundColor Cyan

npm run dev -- -p 3001
