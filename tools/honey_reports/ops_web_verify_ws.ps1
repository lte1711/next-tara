# ops_web_verify_ws.ps1
# ëª©ì : /api/ops/test-event ?¸ë¦¬ê±???SSE(/events) ?˜ì‹  ??WS(/ws/events) ?˜ì‹  ì¦ê±° ?˜ì§‘

$ErrorActionPreference = "Stop"

$BASE = "http://127.0.0.1:8000"
$SSE  = "$BASE/events"
$WS   = "ws://127.0.0.1:8000/ws/events"
$TRG  = "$BASE/api/ops/test-event"

$ROOT = "C:\projects\NEXT-TRADE"
$OUTD = Join-Path $ROOT "evidence\phase-ops"
New-Item -ItemType Directory -Force -Path $OUTD | Out-Null

$ts = (Get-Date -Format "yyyyMMdd_HHmmss") + "-" + (Get-Random -Maximum 10000)
$out_base = Join-Path $OUTD "VAL-OPS-WS-SSE-$ts"
$out_master = "$out_base.log"
$out_sse = "$out_base.sse.log"
$out_ws = "$out_base.ws.log"
$out_trigger = "$out_base.trigger.log"

"=== VAL-OPS-WS-SSE START $ts ===" | Out-File -FilePath $out_master -Encoding utf8

# 1) WS listener (node ws_probe.mjs ?œìš©)
$wsProbeCandidates = @(
  "C:\projects\NEXT-TRADE-UI\tools\ws_probe.mjs",
  (Join-Path $ROOT "tools\ws_probe.mjs")
)

$wsProbe = $wsProbeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

$wsJob = $null
if ($wsProbe) {
  "WS_PROBE=$wsProbe" | Tee-Object -FilePath $out_master -Append
  $wsJob = Start-Job -ScriptBlock {
    param($probe, $wsUrl, $outFile)
    node $probe $wsUrl 10 *>> $outFile
  } -ArgumentList $wsProbe, $WS, $out_ws
} else {
  "WARN: ws_probe.mjs not found. WS capture will be skipped." | Tee-Object -FilePath $out_master -Append
}

Start-Sleep -Seconds 1

# 2) SSE listener (curl)
 $sseJob = Start-Job -ScriptBlock {
  param($sseUrl, $outFile)
  curl.exe --no-buffer $sseUrl 2>&1 | Select-Object -First 50 | Out-File -FilePath $outFile -Append -Encoding utf8
} -ArgumentList $SSE, $out_sse

Start-Sleep -Seconds 1

# 3) Trigger
$metrics_before = "--- METRICS BEFORE ---"
$metrics_before | Tee-Object -FilePath $out_master -Append
try {
  curl.exe -s "$BASE/api/ops/metrics" 2>&1 | Tee-Object -FilePath $out_master -Append
} catch {
  "METRICS_BEFORE_FAIL" | Tee-Object -FilePath $out_master -Append
}

$payload = @{
  message = "ops-test"
  source  = "honey-verify"
} | ConvertTo-Json

"--- TRIGGER POST $TRG ---" | Tee-Object -FilePath $out_trigger -Append
try {
  $resp = Invoke-RestMethod -Method Post -Uri $TRG -ContentType "application/json" -Body $payload
  ($resp | ConvertTo-Json -Depth 10) | Tee-Object -FilePath $out_trigger -Append
} catch {
  "TRIGGER_ERROR: $($_.Exception.Message)" | Tee-Object -FilePath $out_trigger -Append
  throw
}

Start-Sleep -Seconds 3

# 4) Collect jobs
"--- SSE JOB OUTPUT (from $out_sse) ---" | Tee-Object -FilePath $out_master -Append
if (Test-Path $out_sse) { Get-Content $out_sse -ErrorAction SilentlyContinue | Tee-Object -FilePath $out_master -Append }
Stop-Job $sseJob -ErrorAction SilentlyContinue | Out-Null
Remove-Job $sseJob -ErrorAction SilentlyContinue | Out-Null

if ($wsJob) {
  "--- WS JOB OUTPUT (from $out_ws) ---" | Tee-Object -FilePath $out_master -Append
  if (Test-Path $out_ws) { Get-Content $out_ws -ErrorAction SilentlyContinue | Tee-Object -FilePath $out_master -Append }
  Stop-Job $wsJob -ErrorAction SilentlyContinue | Out-Null
  Remove-Job $wsJob -ErrorAction SilentlyContinue | Out-Null
}

"=== VAL-OPS-WS-SSE END ===" | Tee-Object -FilePath $out_master -Append
Write-Host "OK: evidence log -> $out_master"
# --- aggregate remaining info into master file ---
# copy trigger file contents into master
"--- METRICS AFTER ---" | Tee-Object -FilePath $out_master -Append
try {
  curl.exe -s "$BASE/api/ops/metrics" 2>&1 | Tee-Object -FilePath $out_master -Append
} catch {
  "METRICS_AFTER_FAIL" | Tee-Object -FilePath $out_master -Append
}
if (Test-Path $out_trigger) { Get-Content $out_trigger -ErrorAction SilentlyContinue | Tee-Object -FilePath $out_master -Append }
cd C:\projects\NEXT-TRADE
mkdir -Force .\tools\honey_reports | Out-Null
$out = '.\tools\honey_reports\ops_web_verify_ws.txt'
"=== VERIFY_WS START ===" | Out-File $out -Encoding UTF8
"TIME: $(Get-Date -Format s)" | Out-File -Append $out
"=== NETSTAT :8100 ===" | Out-File -Append $out
netstat -ano | findstr :8100 | Out-File -Append $out
"=== UVICORN ERR (head) ===" | Out-File -Append $out
Get-Content .\tools\honey_reports\ops_web_8100.err -ErrorAction SilentlyContinue | Select-Object -First 120 | Out-File -Append $out -Encoding UTF8
"=== UVICORN LOG (head) ===" | Out-File -Append $out
Get-Content .\tools\honey_reports\ops_web_8100.log -ErrorAction SilentlyContinue | Select-Object -First 120 | Out-File -Append $out -Encoding UTF8

"=== ROUTES: openapi.json keys ===" | Out-File -Append $out -Encoding UTF8
try {
  $json = Invoke-RestMethod http://127.0.0.1:8100/openapi.json -TimeoutSec 5
  ($json.paths.PSObject.Properties.Name | Sort-Object) | Select-Object -First 200 | Out-File -Append $out -Encoding UTF8
} catch {
  "OPENAPI_FETCH_FAIL: $($_.Exception.Message)" | Out-File -Append $out -Encoding UTF8
}

# WS probe: use existing tools/ws_probe.mjs if present in NEXT-TRADE-UI
"=== WS_PROBE_CHECK ===" | Out-File -Append $out -Encoding UTF8
$wsProbePath = 'C:\projects\NEXT-TRADE-UI\tools\ws_probe.mjs'
if(Test-Path $wsProbePath) { "WS_PROBE_EXISTS: $wsProbePath" | Out-File -Append $out -Encoding UTF8 } else { "WS_PROBE_MISSING" | Out-File -Append $out -Encoding UTF8 }

# Candidate WS path placeholder (to be set by human if needed)
$wsPath = '/ws/events'
"=== WS_PATH=$wsPath ===" | Out-File -Append $out -Encoding UTF8

# If ws_probe exists, run it
if(Test-Path $wsProbePath) {
  "=== WS_PROBE (node) ===" | Out-File -Append $out -Encoding UTF8
  try {
    Set-Location 'C:\projects\NEXT-TRADE-UI'
    node .\tools\ws_probe.mjs ("ws://127.0.0.1:8100" + $wsPath) 10 2>&1 | Out-File -Append $out -Encoding UTF8
  } catch {
    "WS_PROBE_FAIL: $($_.Exception.Message)" | Out-File -Append $out -Encoding UTF8
  } finally {
    Set-Location 'C:\projects\NEXT-TRADE'
  }
}

"=== TRIGGER_PATH_PLACEHOLDER ===" | Out-File -Append $out -Encoding UTF8
$triggerPath = '/api/ops/test-event'
"=== TRIGGER_PATH=$triggerPath ===" | Out-File -Append $out -Encoding UTF8
try {
  $resp = Invoke-RestMethod ("http://127.0.0.1:8100" + $triggerPath) -Method Post -TimeoutSec 5
  "TRIGGER_OK: $($resp | ConvertTo-Json -Compress)" | Out-File -Append $out -Encoding UTF8
} catch {
  "TRIGGER_FAIL: $($_.Exception.Message)" | Out-File -Append $out -Encoding UTF8
}

"=== UVICORN ERR (tail) ===" | Out-File -Append $out -Encoding UTF8
Get-Content .\tools\honey_reports\ops_web_8100.err -ErrorAction SilentlyContinue | Select-Object -Last 120 | Out-File -Append $out -Encoding UTF8

"=== UVICORN LOG (tail) ===" | Out-File -Append $out -Encoding UTF8
Get-Content .\tools\honey_reports\ops_web_8100.log -ErrorAction SilentlyContinue | Select-Object -Last 120 | Out-File -Append $out -Encoding UTF8

Get-Content $out -TotalCount 400 | Out-Host

# --- SAFE END BLOCK (no backticks) ---
try {
  "=== VAL-OPS-WS-SSE END ===" | Tee-Object -FilePath $out_master -Append
  "OK: evidence master log -> $out_master" | Tee-Object -FilePath $out_master -Append
  Write-Host ("OK: evidence master log -> {0}" -f $out_master)
  exit 0
} catch {
  Write-Host ("END_BLOCK_ERROR: {0}" -f $_.Exception.Message)
  exit 1
}
