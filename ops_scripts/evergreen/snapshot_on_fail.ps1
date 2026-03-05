$ErrorActionPreference = "SilentlyContinue"

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$dstRoot = "C:\projects\NEXT-TRADE\evidence\evergreen"
$marker = Join-Path $dstRoot "last_fail_marker.txt"
$lockPath = Join-Path $dstRoot ".lock_snapshot_on_fail"

if (Test-Path $lockPath) {
  exit 0
}
New-Item -ItemType File -Path $lockPath -Force | Out-Null

function Get-HealthStatus {
  try {
    $obj = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8100/api/v1/ops/health" -TimeoutSec 8).Content | ConvertFrom-Json
    return [string]$obj.status
  } catch {
    return "UNKNOWN"
  }
}

try {
  $healthStatus = Get-HealthStatus
  if ($healthStatus -ne "CRITICAL") {
    return
  }

  # Avoid snapshot spam while staying in same critical streak.
  $nowMinute = Get-Date -Format "yyyyMMdd_HHmm"
  if (Test-Path $marker) {
    $prev = (Get-Content $marker -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($prev -eq $nowMinute) {
      return
    }
  }

  $srcOut = "C:\projects\NEXT-TRADE\logs\runtime\engine_stdout.log"
  $srcErr = "C:\projects\NEXT-TRADE\logs\runtime\engine_stderr.log"
  $fallbackOut = "C:\projects\NEXT-TRADE\logs\runtime\engine_supervisor.log"

  if (Test-Path $srcOut) {
    Copy-Item $srcOut (Join-Path $dstRoot "fail_engine_$ts.log") -Force
  } elseif (Test-Path $fallbackOut) {
    Copy-Item $fallbackOut (Join-Path $dstRoot "fail_engine_$ts.log") -Force
  }

  if (Test-Path $srcErr) {
    Copy-Item $srcErr (Join-Path $dstRoot "fail_engine_err_$ts.log") -Force
  }

  "$nowMinute" | Out-File -Encoding utf8 $marker
} finally {
  Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
}
