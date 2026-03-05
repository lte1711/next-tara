$root = "C:\projects\NEXT-TRADE"
$events = Join-Path $root "logs\runtime\profitmax_v1_events.jsonl"
$summary = Join-Path $root "logs\runtime\profitmax_v1_summary.json"

# Runtime MIX v2 판정 (Windows venv base 페어 허용)
powershell -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\verify_runtime_mix_v2.ps1"
if ($LASTEXITCODE -ne 0) { throw "RUNTIME_MIX_V2_FAIL" }

try { "API_HEALTH=" + (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8100/api/v1/ops/health" -TimeoutSec 5).StatusCode } catch { "API_HEALTH=FAIL " + $_.Exception.Message }
try { "ACCOUNT=" + (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8100/api/investor/account" -TimeoutSec 8).StatusCode } catch { "ACCOUNT=FAIL " + $_.Exception.Message }

if (Test-Path $events) {
  $count = (Get-Content $events).Count
  "EVENTS_FILE=OK count=$count"
  Get-Content $events -Tail 10
} else {
  "EVENTS_FILE=MISSING"
}

if (Test-Path $summary) {
  "SUMMARY_FILE=OK"
  Get-Content $summary
} else {
  "SUMMARY_FILE=MISSING"
}
