Set-Location 'C:\projects\NEXT-TRADE'

# .env 濡쒕뱶
Get-Content '.env' | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
        $kv = $line.Split('=', 2)
        [Environment]::SetEnvironmentVariable($kv[0].Trim(), $kv[1].Trim(), 'Process')
    }
}

# ??alias ?뺢퇋??
$legacyKeyName = 'BINANCE_TESTNET_' + 'API_' + 'KEY'`r`n$legacySecName = 'BINANCE_TESTNET_' + 'API_' + 'SECRET'`r`n$legacyKeyVal = [Environment]::GetEnvironmentVariable($legacyKeyName, 'Process')`r`n$legacySecVal = [Environment]::GetEnvironmentVariable($legacySecName, 'Process')`r`nif ($legacyKeyVal) { $env:BINANCE_TESTNET_KEY_PLACEHOLDER = $legacyKeyVal }
if ($legacySecVal) { $env:BINANCE_TESTNET_SECRET_PLACEHOLDER = $legacySecVal }

$cert = 'C:\projects\NEXT-TRADE\venv\Lib\site-packages\certifi\cacert.pem'
if (Test-Path $cert) {
    $env:SSL_CERT_FILE = $cert
    $env:REQUESTS_CA_BUNDLE = $cert
}

$env:PYTHONPATH = 'C:\projects\NEXT-TRADE\src;C:\projects\NEXT-TRADE\venv\Lib\site-packages'

$logDir = 'C:\projects\NEXT-TRADE\logs\runtime'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$proc = Start-Process `
    -FilePath 'C:\projects\NEXT-TRADE\venv\Scripts\python.exe' `
    -ArgumentList 'C:\projects\NEXT-TRADE\tools\ops\profitmax_v1_runner.py',
                  '--session-hours', '1',
                  '--symbol', 'BTCUSDT',
                  '--max-positions', '1',
                  '--base-qty', '0.001',
                  '--max-position-minutes', '20' `
    -WorkingDirectory 'C:\projects\NEXT-TRADE' `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$logDir\profitmax_v1_stdout.log" `
    -RedirectStandardError  "$logDir\profitmax_v1_stderr.log"

"PROFITMAX_PID=" + $proc.Id


