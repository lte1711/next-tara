param(
    [int]$Port = 8100,
    [switch]$Foreground,
    [switch]$KillExisting,
    [int]$MaxHealthRetries = 10,
    [int]$HealthRetrySec = 1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Exit-WithCode {
    param(
        [int]$Code,
        [string]$Message
    )
    if ($Message) { Write-Host $Message }
    exit $Code
}

function Mask-Value {
    param([string]$Value)
    if ([string]::IsNullOrEmpty($Value)) { return "<EMPTY>" }
    if ($Value.Length -le 8) { return "<SHORT>" }
    return $Value.Substring(0, 4) + "****" + $Value.Substring($Value.Length - 4, 4)
}

function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return $true
    }

    try {
        Get-Content $Path | ForEach-Object {
            if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
            if ($_ -match '^\s*export\s+([^=]+)\s*=\s*(.*)\s*$' -or $_ -match '^\s*([^=]+)\s*=\s*(.*)\s*$') {
                $name = $matches[1].Trim()
                $value = $matches[2].Trim().Trim('"').Trim("'")
                [Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
        return $true
    } catch {
        return $false
    }
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$venvPython = Join-Path $projectRoot ".venv\\Scripts\\python.exe"
if (-not (Test-Path $venvPython)) {
    $venvPython = Join-Path $projectRoot "venv\\Scripts\\python.exe"
}
if (-not (Test-Path $venvPython)) {
    Exit-WithCode -Code 2 -Message "venv python not found. Expected .venv\\Scripts\\python.exe or venv\\Scripts\\python.exe"
}

if (-not (Import-DotEnv -Path (Join-Path $projectRoot ".env"))) {
    Exit-WithCode -Code 4 -Message ".env load failed"
}

$env:PYTHONPATH = (Join-Path $projectRoot "src")
$env:REST_BASE = "https://testnet.binancefuture.com"

# Policy: if real key/secret exists, force placeholder vars to the same values.
if (([Environment]::GetEnvironmentVariable(('BINANCE_TESTNET_' + 'API_' + 'KEY'),'Process'))) {
    $env:BINANCE_TESTNET_KEY_PLACEHOLDER = ([Environment]::GetEnvironmentVariable(('BINANCE_TESTNET_' + 'API_' + 'KEY'),'Process'))
}
if (([Environment]::GetEnvironmentVariable(('BINANCE_TESTNET_' + 'API_' + 'SECRET'),'Process'))) {
    $env:BINANCE_TESTNET_SECRET_PLACEHOLDER = ([Environment]::GetEnvironmentVariable(('BINANCE_TESTNET_' + 'API_' + 'SECRET'),'Process'))
} elseif ($env:BINANCE_TESTNET_SECRET) {
    $env:BINANCE_TESTNET_SECRET_PLACEHOLDER = $env:BINANCE_TESTNET_SECRET
}

$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($existing) {
    if ($KillExisting) {
        taskkill /F /PID $existing.OwningProcess | Out-Null
        Start-Sleep -Seconds 1
    } else {
        Exit-WithCode -Code 10 -Message "Port $Port is already in use by PID $($existing.OwningProcess). Stop it first or use -KillExisting."
    }
}

$uvicornArgs = @(
    "-m", "uvicorn",
    "next_trade.api.app:app",
    "--host", "127.0.0.1",
    "--port", "$Port"
)

if ($Foreground) {
    Write-Host "REST_BASE=$env:REST_BASE"
    Write-Host "BINANCE_KEY_ALIAS=$(Mask-Value ([Environment]::GetEnvironmentVariable(('BINANCE_TESTNET_' + 'API_' + 'KEY'),'Process')))"
    Write-Host "BINANCE_TESTNET_KEY_PLACEHOLDER=$(Mask-Value $env:BINANCE_TESTNET_KEY_PLACEHOLDER)"
    Write-Host "Starting uvicorn in foreground on 127.0.0.1:$Port"
    & $venvPython $uvicornArgs
    exit $LASTEXITCODE
}

$runtimeLogDir = Join-Path $projectRoot "logs\\runtime"
New-Item -ItemType Directory -Path $runtimeLogDir -Force | Out-Null
$stdoutPath = Join-Path $runtimeLogDir "api_8100_stdout.log"
$stderrPath = Join-Path $runtimeLogDir "api_8100_stderr.log"

$proc = Start-Process -FilePath $venvPython `
    -ArgumentList $uvicornArgs `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -PassThru

Start-Sleep -Seconds 2

if ($proc.HasExited) {
    Exit-WithCode -Code 3 -Message "uvicorn exited early. Check: $stderrPath"
}

$portReady = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.OwningProcess -eq $proc.Id } |
    Select-Object -First 1

if (-not $portReady) {
    Exit-WithCode -Code 3 -Message "uvicorn started (PID $($proc.Id)) but port $Port is not listening."
}

$account = $null
$health = $null
for ($i = 0; $i -lt $MaxHealthRetries; $i++) {
    try {
        $account = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/api/investor/account" -TimeoutSec 10
        $health = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/api/v1/ops/health" -TimeoutSec 10
        if ($account.StatusCode -eq 200 -and $health.StatusCode -eq 200) {
            break
        }
    } catch {
        Start-Sleep -Seconds $HealthRetrySec
    }
}

if (-not $account -or -not $health -or $account.StatusCode -ne 200 -or $health.StatusCode -ne 200) {
    Exit-WithCode -Code 3 -Message "Health checks failed after $MaxHealthRetries retries. Check: $stderrPath"
}

Write-Host "PID=$($proc.Id)"
Write-Host "PORT=$Port LISTEN=OK"
Write-Host "REST_BASE=$env:REST_BASE"
Write-Host "BINANCE_KEY_ALIAS=$(Mask-Value ([Environment]::GetEnvironmentVariable(('BINANCE_TESTNET_' + 'API_' + 'KEY'),'Process')))"
Write-Host "BINANCE_TESTNET_KEY_PLACEHOLDER=$(Mask-Value $env:BINANCE_TESTNET_KEY_PLACEHOLDER)"
Write-Host "/api/investor/account STATUS=$($account.StatusCode)"
Write-Host "/api/v1/ops/health STATUS=$($health.StatusCode)"
Write-Host "STDOUT_LOG=$stdoutPath"
Write-Host "STDERR_LOG=$stderrPath"
exit 0

