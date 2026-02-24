# C:\projects\NEXT-TRADE\tools\runbooks\start_ui.ps1
param(
  [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host "=== NEXT-TRADE UI START (3001) ==="

# 프로젝트가 monorepo일 수도 있으니, 아래 두 경로 중 존재하는 곳에서 실행
$paths = @(
  "C:\projects\NEXT-TRADE-UI",
  "C:\projects\NEXT-TRADE"
)

$uiRoot = $null
foreach ($p in $paths) {
  if (Test-Path $p) { $uiRoot = $p; break }
}

if (-not $uiRoot) {
  throw "UI root not found. Checked: $($paths -join ', ')"
}

Set-Location $uiRoot

Write-Host "Checking port 3001..."
$existing = Get-NetTCPConnection -LocalPort 3001 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existing) {
  $pid = $existing.OwningProcess
  if (-not $Force) {
    Write-Host "Port 3001 already in use (PID=$pid). Skipping start. Use -Force to restart."
    return
  }
  Write-Host "Port 3001 in use (PID=$pid). Stopping..."
  Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 1
}

# Next dev 실행 (프로젝트 스크립트가 있으면 npm run dev, 아니면 npx next dev)
if (Test-Path ".\package.json") {
  $pkg = Get-Content ".\package.json" -Raw
  if ($pkg -match '"dev"\s*:') {
    Write-Host "Running: npm run dev -- --port 3001"
    npm run dev -- --port 3001
  } else {
    Write-Host "Running: npx next dev --port 3001"
    npx next dev --port 3001
  }
} else {
  throw "package.json not found in $uiRoot"
}
