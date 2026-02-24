# [총괄 지시서] S4-A T+2h 재기동 체크포인트 패치 반영

문서번호: NEXT-TRADE-S4A-HOTPATCH-T2H-001
발신: 총괄 백설
집행: 허니(Honey)
승인: Dennis(완료 보고 수령)
원칙: 현재 엔진 무중단 유지 → T+2h 체크포인트에서만 재기동

---

## 0) 현재 상황 고정

- S4-A 엔진 PID: 6820
- Start(KST): 2026-02-24 15:41:18
- 스케줄러: tools\s4a_checkpoint_scheduler.ps1 백그라운드 실행 중
- 모니터링:
  - 프로세스 생존 모니터(30s)
  - execution_audit.jsonl tail

지금은 절대 중단 금지(T+2h까지 유지)

---

## 1) 지금 당장 할 일: 코드만 준비(재기동 없음)

### A. 패치 적용 대상 3종

1. S4 전용 run_id 분리
2. audit JSONL 원자성 보장
3. exit 중복 호출 방지 쿨다운(3초)

### B. 패치 적용 파일

- src/next_trade/runtime/execution_binance_testnet.py
  - run_id 생성 규칙(S4 prefix)
  - audit append 원자성(lock + flush)
- src/next_trade/runtime/live_s2b_engine.py
  - exit 쿨다운(중복 exit 호출 억제)

### C. 로컬 검증(재기동 없이 가능)

```powershell
cd C:\projects\NEXT-TRADE
C:\projects\NEXT-TRADE\venv\Scripts\python.exe -m py_compile `
  src/next_trade/runtime/execution_binance_testnet.py `
  src/next_trade/runtime/live_s2b_engine.py
```

### D. Git 상태(커밋은 T+2h 직전에)

```powershell
cd C:\projects\NEXT-TRADE
git status --porcelain
```

---

## 2) T+2h 체크포인트: 재기동 + 패치 반영(필수)

### A. 재기동 직전: 상태 스냅샷(증거)

```powershell
cd C:\projects\NEXT-TRADE
$kst = [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId((Get-Date), "Korea Standard Time")
"[T+2h PRE] KST=$($kst.ToString('yyyy-MM-dd HH:mm:ss'))" | Write-Host
Get-Process -Id 6820 | Select-Object Id,ProcessName,StartTime | Format-Table
Get-Content .\evidence\phase-s3-runtime\execution_audit.jsonl -Tail 10
```

### B. 안전 종료(강제 종료 금지 → 먼저 정상 종료 시도)

```powershell
Stop-Process -Id 6820
Start-Sleep -Seconds 2
Get-Process -Id 6820 -ErrorAction SilentlyContinue
```

### C. (중요) FIXED_RUN_ID/클린업 환경변수 정리

```powershell
$env:NEXT_TRADE_FIXED_RUN_ID=""
$env:NEXT_TRADE_CLEAR_AUDIT="0"
```

### D. 재기동(새 PID 확보)

```powershell
cd C:\projects\NEXT-TRADE
Get-Content .\.env | ForEach-Object {
  if ($_ -match "^\s*#" -or $_ -match "^\s*$") { } else {
    $parts = $_ -split "=",2
    if ($parts.Count -eq 2) {
      [System.Environment]::SetEnvironmentVariable($parts[0], $parts[1], "Process")
    }
  }
}

$env:NEXT_TRADE_LIVE_TRADING="1"
$proc = Start-Process -FilePath "C:\projects\NEXT-TRADE\venv\Scripts\python.exe" `
  -ArgumentList "-m next_trade.runtime.live_s2b_engine" `
  -WorkingDirectory "C:\projects\NEXT-TRADE" -PassThru

$kst = [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId((Get-Date), "Korea Standard Time")
Write-Host ("[T+2h POST START] KST={0} NEW_PID={1}" -f $kst.ToString("yyyy-MM-dd HH:mm:ss"), $proc.Id)
```

---

## 3) 재기동 직후 즉시 확인해야 할 3가지(증거 제출)

### 증거 1) run*id가 S4*로 시작

```powershell
Get-Content .\evidence\phase-s3-runtime\execution_audit.jsonl -Tail 20
```

### 증거 2) audit JSON 깨짐 0건

```powershell
python - << 'PY'
import json, pathlib
p = pathlib.Path("evidence/phase-s3-runtime/execution_audit.jsonl")
bad=0
for i,line in enumerate(p.read_text(encoding="utf-8").splitlines(),1):
    try: json.loads(line)
    except Exception: bad += 1
print("BAD_LINES=", bad)
PY
```

### 증거 3) OK_DUPLICATE 난사 억제(쿨다운 적용)

```powershell
Get-Content .\evidence\phase-s3-runtime\execution_audit.jsonl -Tail 50
```

---

## 4) 완료 보고 포맷(허니 → Dennis/백설)

1. T+2h PRE KST + old PID
2. T+2h POST KST + new PID
3. run*id S4* 증거 1줄
4. BAD_LINES=0 출력
5. tail 10~20줄(중복난사 여부)
6. git status --porcelain 출력

---

## 5) 절대 금지

- T+2h 이전 강제 재기동 금지
- audit 파일 임의 삭제 금지
- FIXED_RUN_ID를 S3 값으로 유지 금지

---

## 결론

- 지금은 코드 준비만
- T+2h 재시작 체크포인트에서 반영/재기동
- 재기동 직후 run*id(S4*) + JSON 무결성 + 중복 억제 증거 제출
