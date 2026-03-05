Set-Location C:\projects\NEXT-TRADE

# 8100 관련 모든 python 프로세스 완전 정리
$pids8100 = @()
$lines = netstat -ano | Select-String ":8100"
foreach ($l in $lines) {
    $p = ($l.Line -split "\s+")[-1]
    if ($p -match "^\d+$" -and $p -ne "0") { $pids8100 += [int]$p }
}
$pids8100 = $pids8100 | Sort-Object -Unique
foreach ($p in $pids8100) {
    "KILL_8100_PID=$p"
    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
}

# uvicorn 관련 python 전부 추가 정리
Get-CimInstance Win32_Process | ForEach-Object {
    $cl = $_.CommandLine
    if ($cl -and ($cl -match "uvicorn.*next_trade|next_trade.*uvicorn")) {
        "KILL_UVICORN_PID=$($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 2

# .env 로드
if (Test-Path '.env') {
    Get-Content '.env' | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
            $kv = $line.Split('=', 2)
            [Environment]::SetEnvironmentVariable($kv[0].Trim(), $kv[1].Trim(), 'Process')
        }
    }
}

$cert = 'C:\projects\NEXT-TRADE\venv\Lib\site-packages\certifi\cacert.pem'
$env:SSL_CERT_FILE = $cert
$env:REQUESTS_CA_BUNDLE = $cert
$env:PYTHONPATH = 'C:\projects\NEXT-TRADE\src;C:\projects\NEXT-TRADE\venv\Lib\site-packages'

$proc = Start-Process `
    -FilePath 'C:\projects\NEXT-TRADE\venv\Scripts\python.exe' `
    -ArgumentList '-m', 'uvicorn', 'next_trade.api.app:app', '--host', '127.0.0.1', '--port', '8100', '--log-level', 'info' `
    -WorkingDirectory 'C:\projects\NEXT-TRADE' `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput 'C:\projects\NEXT-TRADE\svc_api_8100_stdout.log' `
    -RedirectStandardError 'C:\projects\NEXT-TRADE\svc_api_8100_stderr.log'

"STARTED_PID=" + $proc.Id
