Param()

$ErrorActionPreference = 'Continue'

$logDir = "C:\projects\NEXT-TRADE-UI\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

$logFile = Join-Path $logDir 'ui_health_check.log'
$url = 'http://127.0.0.1:3000/institutional'

function Write-Log($msg) {
  $t = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
  $line = "[$t] $msg"
  $line | Out-File -FilePath $logFile -Encoding utf8 -Append
  Write-Output $line
}

try {
  $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
  $status = $resp.StatusCode
  $len = ($resp.Content | Measure-Object -Character).Characters
  Write-Log "OK HTTP $status, body ${len} chars"
} catch {
  $err = $_.Exception.Message
  Write-Log "ERROR: $err"
  try {
    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $failFile = Join-Path $logDir "ui_health_failed_$timestamp.html"
    # attempt to save response body if present
    if ($_.Exception.Response -and $_.Exception.Response.GetResponseStream()) {
      $_.Exception.Response | Out-File -FilePath $failFile -Encoding utf8 -Force
      Write-Log "Saved failure HTML to $failFile"
    }
  } catch {
    Write-Log "Failed to save failure HTML: $($_.Exception.Message)"
  }
}
