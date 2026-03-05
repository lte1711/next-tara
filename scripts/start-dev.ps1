$ErrorActionPreference = "Stop"

Set-Location (Split-Path $PSScriptRoot -Parent)
$env:NEXT_TELEMETRY_DISABLED = "1"

# Contract base must be pinned to the contract API.
$envFile = ".env.local"
if (!(Test-Path $envFile)) { throw "Missing .env.local (NEXT_PUBLIC_CONTRACT_BASE required)" }
$envText = Get-Content $envFile -Raw
if ($envText -notmatch "NEXT_PUBLIC_CONTRACT_BASE=http://127\.0\.0\.1:8100") {
  throw "Invalid NEXT_PUBLIC_CONTRACT_BASE in .env.local"
}

if (Test-Path .next) { Remove-Item .next -Recurse -Force -ErrorAction SilentlyContinue }
if (Test-Path .turbo) { Remove-Item .turbo -Recurse -Force -ErrorAction SilentlyContinue }

# Operational standard: port 3001.
# Next 14 does not support --no-turbo flag; default dev server is used.
npx next dev -p 3001
