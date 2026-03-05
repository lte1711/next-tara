# PMX Boot Strap: venv PATH enforce (NO CODE CHANGE)
$root = "C:\projects\NEXT-TRADE"
$venv = Join-Path $root "venv\Scripts"
$py   = Join-Path $venv "python.exe"

if (-not (Test-Path $py)) { throw "VENV python not found: $py" }

# 핵심: PATH 맨 앞에 venv\Scripts 강제
$env:PATH = "$venv;$env:PATH"
$env:PYTHONHOME = ""
$env:PYTHONPATH = ""

Write-Host "=== EFFECTIVE PYTHON ==="
where.exe python
python -c "import sys; print('SYS_EXEC=', sys.executable)"

Write-Host "=== START API 8100 (uvicorn) ==="
Start-Process -FilePath $py -ArgumentList "-m","uvicorn","ops_web.app:app","--host","127.0.0.1","--port","8100" -WorkingDirectory $root

Write-Host "=== START PMX RUNNER ==="
Start-Process -FilePath $py -ArgumentList "tools\ops\profitmax_v1_runner.py" -WorkingDirectory $root
