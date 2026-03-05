$ErrorActionPreference = "SilentlyContinue"

# If port 8100 is listening, do nothing.
$line = netstat -ano | findstr /r /c:":8100 .*LISTENING" | Select-Object -First 1
if ($line) {
  exit 0
}

# Port not listening -> try start scheduled task (preferred)
schtasks /Run /TN NEXTTRADE_API_8100 | Out-Null
Start-Sleep -Seconds 2

# Re-check
$line2 = netstat -ano | findstr /r /c:":8100 .*LISTENING" | Select-Object -First 1
if ($line2) {
  exit 0
}

# Fallback: direct cmd launch
cmd /c "C:\projects\NEXT-TRADE\tools\ops\run_api_8100.cmd" | Out-Null
exit 0
