# S4-A snapshot capture helper
# Saves runtime_state.json, alerts tail, and audit tail to evidence/phase-s4-pilot

$ErrorActionPreference = "Stop"

$projectRoot = "C:\projects\NEXT-TRADE"
$evidenceDir = Join-Path $projectRoot "evidence\phase-s4-pilot"

if (-not (Test-Path $evidenceDir)) {
    New-Item -ItemType Directory -Path $evidenceDir | Out-Null
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

$stateSrc = Join-Path $projectRoot "var\runtime_state.json"
$alertsSrc = Join-Path $projectRoot "evidence\phase-s3-runtime\alerts.jsonl"
$auditSrc = Join-Path $projectRoot "evidence\phase-s3-runtime\execution_audit.jsonl"

$stateDst = Join-Path $evidenceDir "state_$stamp.json"
$alertsDst = Join-Path $evidenceDir "alerts_tail_$stamp.jsonl"
$auditDst = Join-Path $evidenceDir "audit_tail_$stamp.jsonl"

if (Test-Path $stateSrc) {
    Get-Content $stateSrc | Set-Content $stateDst -Encoding utf8
}

if (Test-Path $alertsSrc) {
    Get-Content $alertsSrc -Tail 200 | Set-Content $alertsDst -Encoding utf8
}

if (Test-Path $auditSrc) {
    Get-Content $auditSrc -Tail 200 | Set-Content $auditDst -Encoding utf8
}

Write-Host ("[S4-A SNAPSHOT] {0}" -f $stamp)
Write-Host ("State:  {0}" -f $stateDst)
Write-Host ("Alerts: {0}" -f $alertsDst)
Write-Host ("Audit:  {0}" -f $auditDst)
