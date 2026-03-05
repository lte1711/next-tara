Set-Location C:\projects\NEXT-TRADE

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
$env:PYTHONPATH = 'C:\projects\NEXT-TRADE\src'

$proc = Start-Process `
    -FilePath 'C:\projects\NEXT-TRADE\venv\Scripts\python.exe' `
    -ArgumentList '-m', 'uvicorn', 'next_trade.api.app:app', '--host', '127.0.0.1', '--port', '8100', '--log-level', 'info' `
    -WorkingDirectory 'C:\projects\NEXT-TRADE' `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput 'C:\projects\NEXT-TRADE\svc_api_8100_stdout.log' `
    -RedirectStandardError 'C:\projects\NEXT-TRADE\svc_api_8100_stderr.log'

"STARTED_PID=" + $proc.Id
