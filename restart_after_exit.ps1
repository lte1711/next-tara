Set-Location C:\projects\NEXT-TRADE

Write-Host "Polling for position close..."

$maxWaitSec = 1800
$elapsed = 0

while ($elapsed -lt $maxWaitSec) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8100/api/profitmax/status?limit=1" -UseBasicParsing -TimeoutSec 5
        $data = $resp.Content | ConvertFrom-Json
        $posOpen = $data.summary.position_open
        $pnl = $data.summary.session_realized_pnl
        Write-Host ("  " + (Get-Date -Format "HH:mm:ss") + " position_open=" + $posOpen + " pnl=" + $pnl)
        if (-not $posOpen) {
            Write-Host "Position closed! Restarting runner..."
            break
        }
    } catch {
        Write-Host "  API error: $_"
    }
    Start-Sleep -Seconds 10
    $elapsed += 10
}

# Kill old runner (PID 4376 or any profitmax runner)
$runnerLock = 'C:\projects\NEXT-TRADE\logs\runtime\profitmax_v1.lock'
if (Test-Path $runnerLock) {
    try {
        $lockData = Get-Content $runnerLock | ConvertFrom-Json
        $oldPid = $lockData.pid
        if ($oldPid) {
            Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
            Write-Host "Killed old runner PID $oldPid"
        }
    } catch {}
    Remove-Item $runnerLock -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 3

# Load .env
if (Test-Path '.env') {
    Get-Content '.env' | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
            $kv = $line.Split('=', 2)
            [Environment]::SetEnvironmentVariable($kv[0].Trim(), $kv[1].Trim(), 'Process')
        }
    }
}

if (-not $env:BINANCE_TESTNET_KEY_PLACEHOLDER -and ([Environment]::GetEnvironmentVariable(('BINANCE_TESTNET_' + 'API_' + 'KEY'),'Process'))) {
    $env:BINANCE_TESTNET_KEY_PLACEHOLDER = ([Environment]::GetEnvironmentVariable(('BINANCE_TESTNET_' + 'API_' + 'KEY'),'Process'))
}
if (-not $env:BINANCE_TESTNET_SECRET_PLACEHOLDER -and ([Environment]::GetEnvironmentVariable(('BINANCE_TESTNET_' + 'API_' + 'SECRET'),'Process'))) {
    $env:BINANCE_TESTNET_SECRET_PLACEHOLDER = ([Environment]::GetEnvironmentVariable(('BINANCE_TESTNET_' + 'API_' + 'SECRET'),'Process'))
}

$cert = 'C:\projects\NEXT-TRADE\venv\Lib\site-packages\certifi\cacert.pem'
if (Test-Path $cert) {
    $env:SSL_CERT_FILE = $cert
    $env:REQUESTS_CA_BUNDLE = $cert
}

$env:PYTHONPATH = 'C:\projects\NEXT-TRADE\src;C:\projects\NEXT-TRADE\venv\Lib\site-packages'

$logDir = 'C:\projects\NEXT-TRADE\logs\runtime'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# Archive old logs
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
if (Test-Path "$logDir\profitmax_v1_events.jsonl") {
    Copy-Item "$logDir\profitmax_v1_events.jsonl" "$logDir\profitmax_v1_events_$ts.jsonl"
}

$proc = Start-Process `
    -FilePath 'C:\projects\NEXT-TRADE\venv\Scripts\python.exe' `
    -ArgumentList 'C:\projects\NEXT-TRADE\tools\ops\profitmax_v1_runner.py',
                  '--session-hours', '1.5',
                  '--symbol', 'BTCUSDT',
                  '--max-positions', '1',
                  '--base-qty', '0.001',
                  '--max-position-minutes', '20' `
    -WorkingDirectory 'C:\projects\NEXT-TRADE' `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$logDir\profitmax_v1_stdout.log" `
    -RedirectStandardError  "$logDir\profitmax_v1_stderr.log"

Write-Host ("NEW RUNNER PID=" + $proc.Id + " (10-min timeout, 1.5h session)")

