# NEXT-TRADE-UI Clean Restart Script
# WebSocket 연결 강제 반영용

Write-Host "=== NEXT-TRADE-UI Clean Restart ===" -ForegroundColor Cyan

# 1) Next.js dev 서버 종료 (포트 3000)
Write-Host "`n1. Stopping Next.js dev server (port 3000)..." -ForegroundColor Yellow
$procs = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
if ($procs) {
    $procs | ForEach-Object {
        $procId = $_.OwningProcess
        Write-Host "   Killing PID $procId" -ForegroundColor Gray
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
} else {
    Write-Host "   No process on port 3000" -ForegroundColor Gray
}

# 2) .next 캐시 삭제
Write-Host "`n2. Removing .next cache..." -ForegroundColor Yellow
$nextDir = "C:\projects\NEXT-TRADE-UI\.next"
if (Test-Path $nextDir) {
    Remove-Item -Recurse -Force $nextDir
    Write-Host "   ✓ .next removed" -ForegroundColor Green
} else {
    Write-Host "   .next not found (OK)" -ForegroundColor Gray
}

# 3) 환경변수 확인
Write-Host "`n3. Checking .env.local..." -ForegroundColor Yellow
$envFile = "C:\projects\NEXT-TRADE-UI\.env.local"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "NEXT_PUBLIC_WS_URL") {
            Write-Host "   $_" -ForegroundColor Cyan
        }
    }
} else {
    Write-Host "   ⚠️  .env.local not found!" -ForegroundColor Red
}

# 4) dev 서버 시작 준비
Write-Host "`n4. Ready to start dev server" -ForegroundColor Yellow
Write-Host "   Run this command manually:" -ForegroundColor White
Write-Host "   cd C:\projects\NEXT-TRADE-UI && npm run dev" -ForegroundColor Cyan
Write-Host ""
Write-Host "=== Clean restart preparation complete ===" -ForegroundColor Green
Write-Host "After starting dev server, do Ctrl+Shift+R in browser!" -ForegroundColor Yellow
