@echo off
setlocal

REM --- Hardening ---
set "ROOT=C:\projects\NEXT-TRADE"
set "PYTHONPATH=%ROOT%\src"
set "PATH=%ROOT%\venv\Scripts;%PATH%"

cd /d "%ROOT%"

REM --- Port guard: if already listening, exit OK ---
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":8100 .*LISTENING"') do (
  echo API_8100_ALREADY_LISTENING PID=%%a
  exit /b 0
)

REM --- Start API ---
"%ROOT%\venv\Scripts\python.exe" -m uvicorn next_trade.api.app:app --host 127.0.0.1 --port 8100

REM --- Keep TaskScheduler result stable even if process exits unexpectedly ---
exit /b 0
