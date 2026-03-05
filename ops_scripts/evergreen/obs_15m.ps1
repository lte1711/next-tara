$ErrorActionPreference = "SilentlyContinue"

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$outPath = "C:\projects\NEXT-TRADE\evidence\evergreen\obs_15m_$ts.txt"
$tmpPath = "$outPath.tmp"
$lockPath = "C:\projects\NEXT-TRADE\evidence\evergreen\.lock_obs_15m"

if (Test-Path $lockPath) {
  exit 0
}
New-Item -ItemType File -Path $lockPath -Force | Out-Null

function Get-ContentOrErr([string]$url) {
  try {
    return (Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 10).Content
  } catch {
    return "ERR: $($_.Exception.Message)"
  }
}

try {
  $health = Get-ContentOrErr "http://127.0.0.1:8100/api/v1/ops/health"
  $pos = Get-ContentOrErr "http://127.0.0.1:8100/api/v1/trading/positions"
  $orders = Get-ContentOrErr "http://127.0.0.1:8100/api/v1/trading/open_orders"

  $out = @()
  $out += "STAMP=OBS15M_$ts"
  $out += "HEALTH=$health"
  $out += "POSITIONS=$pos"
  $out += "ORDERS=$orders"

  $out | Out-File -Encoding utf8 $tmpPath
  Move-Item -Force $tmpPath $outPath
} finally {
  Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
}
