Set-Location C:\projects\NEXT-TRADE

# .env 濡쒕뱶
function Load-Env {
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
}

function Start-Runner {
    $logDir = 'C:\projects\NEXT-TRADE\logs\runtime'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null

    # 湲곗〈 lock ?뚯씪??PID ?뺤씤 ??醫낅즺
    $lockPath = "$logDir\profitmax_v1.lock"
    if (Test-Path $lockPath) {
        try {
            $lockData = Get-Content $lockPath | ConvertFrom-Json
            $oldPid = $lockData.pid
            if ($oldPid) {
                Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
                Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Killed old runner PID $oldPid"
            }
        } catch {}
        Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }

    # ?댁쟾 濡쒓렇 ?꾩뭅?대툕
    $ts = Get-Date -Format 'yyyyMMdd_HHmmss'
    foreach ($f in @('profitmax_v1_events.jsonl', 'profitmax_v1_summary.json')) {
        $src = "$logDir\$f"
        if (Test-Path $src) {
            Copy-Item $src "$logDir\${f}_$ts" -ErrorAction SilentlyContinue
        }
    }

    Load-Env

    $proc = Start-Process `
        -FilePath 'C:\projects\NEXT-TRADE\venv\Scripts\python.exe' `
        -ArgumentList 'C:\projects\NEXT-TRADE\tools\ops\profitmax_v1_runner.py',
                      '--session-hours', '6',
                      '--symbol', 'BTCUSDT',
                      '--max-positions', '1',
                      '--base-qty', '0.001',
                      '--max-position-minutes', '20' `
        -WorkingDirectory 'C:\projects\NEXT-TRADE' `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$logDir\profitmax_v1_stdout.log" `
        -RedirectStandardError  "$logDir\profitmax_v1_stderr.log"

    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Runner started PID=$($proc.Id) (6h session, 10min timeout)"
    return $proc
}

Write-Host "=== PROFITMAX DAEMON STARTED ==="
Write-Host "Sessions: 6h each, auto-restart on exit"

# ?꾩옱 ?ㅽ뻾 以묒씤 runner媛 ?덉쑝硫?醫낅즺 ?湲? ?놁쑝硫?諛붾줈 ?쒖옉
$lockPath = 'C:\projects\NEXT-TRADE\logs\runtime\profitmax_v1.lock'
$waitForCurrent = $false
if (Test-Path $lockPath) {
    try {
        $lockData = Get-Content $lockPath | ConvertFrom-Json
        $existingPid = $lockData.pid
        $proc = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Existing runner PID=$existingPid found, waiting for session end..."
            $waitForCurrent = $true
        }
    } catch {}
}

if ($waitForCurrent) {
    # ?꾩옱 ?몄뀡???앸궇 ?뚭퉴吏 ?湲?
    while ($true) {
        Start-Sleep -Seconds 30
        if (-not (Test-Path $lockPath)) {
            Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Session ended, starting new session..."
            break
        }
        try {
            $lockData = Get-Content $lockPath | ConvertFrom-Json
            $pid2 = $lockData.pid
            $p2 = Get-Process -Id $pid2 -ErrorAction SilentlyContinue
            if (-not $p2) {
                Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Session ended (PID gone), starting new session..."
                break
            }
        } catch {
            break
        }
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Still running PID=$pid2 ..."
    }
}

# 硫붿씤 猷⑦봽: ?몄뀡???앸굹硫??먮룞 ?ъ떆??
while ($true) {
    $proc = Start-Runner
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Waiting for session to complete..."
    $proc.WaitForExit()
    $exitCode = $proc.ExitCode
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Session ended (exit=$exitCode). Restarting in 5s..."
    Start-Sleep -Seconds 5
}

