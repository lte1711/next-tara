param(
  [string]$ProjectRoot = "C:\projects\NEXT-TRADE",
  [string]$EvidenceDir = "C:\projects\NEXT-TRADE\evidence\pmx",
  [int]$ProbeSleepSec = 3
)

$ErrorActionPreference = "Stop"

function NowStamp() {
  return (Get-Date -Format "yyyyMMdd_HHmmss")
}

$stamp = NowStamp
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$reportJsonl = Join-Path $EvidenceDir ("runtime_self_report_" + $stamp + ".jsonl")
$treeTxt     = Join-Path $EvidenceDir ("runtime_tree_" + $stamp + ".txt")
$verdictTxt  = Join-Path $EvidenceDir ("runtime_mix_verdict_" + $stamp + ".txt")

$venvPy = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$probePy = Join-Path $ProjectRoot "tools\ops\runtime_self_report.py"

if (!(Test-Path $venvPy)) { throw "venv python not found: $venvPy" }
if (!(Test-Path $probePy)) { throw "probe script not found: $probePy" }

"RUN_START=$stamp" | Out-File -Encoding utf8 $verdictTxt

# 1) Probe 실행(별도 프로세스 유지로 트리 캡처)
#    - Windows venv launcher 환경에서는 stdout 캡처가 비는 경우가 있어 파일 기록(--out)도 함께 사용
$probeOut = & $venvPy $probePy --sleep $ProbeSleepSec --tag "pmx_runtime_mix_v2" --out $reportJsonl
if ($probeOut) {
  $probeOut | Out-File -Encoding utf8 $reportJsonl
}

# 2) 방금 실행된 probe 프로세스(아직 살아있거나 방금 종료된) 트리 캡처
#    - 종료가 너무 빨라서 누락될 수 있으니 ProbeSleepSec로 완화
Start-Sleep -Milliseconds 200

# CommandLine에 runtime_self_report.py 포함된 python 프로세스 검색
$procs = Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -and ($_.CommandLine -match "runtime_self_report\.py") } |
  Select-Object ProcessId, ParentProcessId, ExecutablePath, CommandLine

# 만약 probe가 이미 종료되어 procs가 비면, "최근 출력된 self_report"를 기준으로 판정은 계속 진행하고,
# 트리 증거는 별도 경고로 남김.
$treeLines = @()
$treeLines += "=== RUNTIME_TREE_CAPTURE ts=$stamp ==="
if ($procs -and $procs.Count -gt 0) {
  $treeLines += ($procs | Format-Table -AutoSize | Out-String)
} else {
  $treeLines += "WARN: runtime_self_report.py process not found at capture time (likely exited)."
}
$treeLines | Out-File -Encoding utf8 $treeTxt

# 3) Self-report JSON 파싱
$jsonLine = $null
if ($probeOut) {
  $jsonLine = ($probeOut | Select-Object -Last 1)
}
if (-not $jsonLine -and (Test-Path $reportJsonl)) {
  $jsonLine = (Get-Content $reportJsonl | Where-Object { $_.Trim() } | Select-Object -Last 1)
}
try {
  $jr = $jsonLine | ConvertFrom-Json
} catch {
  "FAIL reason=self_report_json_parse_error" | Add-Content -Encoding utf8 $verdictTxt
  "RUN_END=$stamp" | Add-Content -Encoding utf8 $verdictTxt
  Write-Host "FINAL_VERDICT=FAIL"
  exit 1
}

$sysExe  = [string]$jr.sys_executable
$baseExe = [string]$jr.sys_base_executable

# 4) 판정 규칙 v2
# PASS 조건:
#  - sys.executable 이 venv python을 가리키면 PASS (Windows에서는 base_executable이 시스템 Python이어도 허용)
# FAIL 조건:
#  - sys.executable 이 venv가 아니면 FAIL
$venvOk = $false
if ($sysExe -and ($sysExe.ToLower() -eq $venvPy.ToLower())) { $venvOk = $true }

if (-not $venvOk) {
  "FAIL reason=sys_executable_not_venv sys_executable=$sysExe expected=$venvPy base_executable=$baseExe" | Add-Content -Encoding utf8 $verdictTxt
  "RUN_END=$stamp" | Add-Content -Encoding utf8 $verdictTxt
  Write-Host "FINAL_VERDICT=FAIL"
  exit 2
}

# 강화: base_executable이 시스템 python이어도 PASS지만, 기록은 남김
"PASS reason=windows_venv_base_pair_allowed sys_executable=$sysExe base_executable=$baseExe" | Add-Content -Encoding utf8 $verdictTxt
"ARTIFACT_self_report=$reportJsonl" | Add-Content -Encoding utf8 $verdictTxt
"ARTIFACT_tree=$treeTxt" | Add-Content -Encoding utf8 $verdictTxt
"RUN_END=$stamp" | Add-Content -Encoding utf8 $verdictTxt

Write-Host "FINAL_VERDICT=PASS"
exit 0
