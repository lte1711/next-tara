# [총괄 지시서] PHASE-S4-A 72H Live Pilot 운영 지침서 (TESTNET LIVE)

문서번호: NEXT-TRADE-S4A-RUNBOOK-001
발신: 총괄 백설
집행: 허니(Honey)
승인/서버명령: Dennis
효력: 즉시 (S4-A START: 2026-02-24 15:41:18 KST, PID 6820)

---

## 0) 현재 상태 확정

- 엔트리포인트: `python -m next_trade.runtime.live_s2b_engine`
- 모드: TESTNET LIVE
- PID: 6820
- 환경:
  - `NEXT_TRADE_LIVE_TRADING=1`
  - `NEXT_TRADE_CLEAR_AUDIT=0`
  - `NEXT_TRADE_FIXED_RUN_ID=""` (미사용)

위 상태는 정상 진행이며, 72H 동안 운영 이벤트(재시작/네트워크/킬스위치)를 증거로 남기는 운영 검증이다.

---

## 1) 즉시 해야 할 증거 자동 수집 (필수)

### 1-A. 표준 로그 파일로 리다이렉트 (권장)

현재 Start-Process 방식으로 기동 중이므로, 다음 재시작(T+2h)부터는 반드시 파일 리다이렉트 방식으로 전환한다.

```powershell
cd C:\projects\NEXT-TRADE
mkdir -Force .\evidence\phase-s4-pilot | Out-Null

# T+2h 재시작부터 적용
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$log = "evidence\phase-s4-pilot\s4a_engine_$stamp.log"

# .env 로드 + env 세팅 후, 파일 리다이렉트로 실행
Get-Content .\.env | ForEach-Object {
  if ($_ -match "^\s*#" -or $_ -match "^\s*$") { return }
  $parts = $_ -split "=",2
  if ($parts.Count -eq 2) { [Environment]::SetEnvironmentVariable($parts[0], $parts[1], "Process") }
}

$env:NEXT_TRADE_LIVE_TRADING="1"
$env:NEXT_TRADE_CLEAR_AUDIT="0"
$env:NEXT_TRADE_FIXED_RUN_ID=""

cmd /c "C:\projects\NEXT-TRADE\venv\Scripts\python.exe -m next_trade.runtime.live_s2b_engine >> $log 2>&1"
```

### 1-B. 상태/알림/감사 로그 스냅샷 루틴

체크포인트마다 아래 3개 파일을 tail 캡처해서 evidence 폴더에 저장한다.

- `var/runtime_state.json`
- `evidence/phase-s3-runtime/alerts.jsonl`
- `evidence/phase-s3-runtime/execution_audit.jsonl`

```powershell
cd C:\projects\NEXT-TRADE
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

Get-Content .\var\runtime_state.json -ErrorAction SilentlyContinue | Set-Content "evidence\phase-s4-pilot\state_$stamp.json" -Encoding utf8
Get-Content .\evidence\phase-s3-runtime\alerts.jsonl -Tail 200 -ErrorAction SilentlyContinue | Set-Content "evidence\phase-s4-pilot\alerts_tail_$stamp.jsonl" -Encoding utf8
Get-Content .\evidence\phase-s3-runtime\execution_audit.jsonl -Tail 200 -ErrorAction SilentlyContinue | Set-Content "evidence\phase-s4-pilot\audit_tail_$stamp.jsonl" -Encoding utf8
```

---

## 2) 체크포인트 집행 지시

### T+2h 체크포인트: 재시작 내성

목표: 프로세스 재기동 후 상태 복구 + 중복 주문 없음 + 엔진 지속

1. 현재 PID 종료

```powershell
Stop-Process -Id 6820 -Force
```

2. 종료 직후 상태/로그 스냅샷(1-B 실행)

3. 리다이렉트 방식으로 재기동(1-A 방식 사용)

4. 재기동 PID/시각 보고 포맷

```
[S4-A T+2h RESTART]
Timestamp (KST):
Old PID:
New PID:
State file exists: (True/False)
Last alert types: (tail로 확인)
```

---

### T+8h 체크포인트: 네트워크 단절 내성

목표: 네트워크 장애 → EXCHANGE_ERROR 기록 + 엔진 생존 + 복구 후 정상화

1. 차단 대상 IP 재조회

```powershell
Resolve-DnsName testnet.binancefuture.com | Select-Object -ExpandProperty IPAddress
```

2. 방화벽 차단 룰 추가 (Outbound 443)

```powershell
New-NetFirewallRule -DisplayName "S4A_BLOCK_TESTNET_443" -Direction Outbound -Action Block -Protocol TCP -RemotePort 443 -RemoteAddress "18.67.51.112,18.67.51.69,18.67.51.61,18.67.51.87"
```

3. 2~3분 유지하면서 alerts/audit에 EXCHANGE_ERROR 발생 확인 → 스냅샷 저장

4. 방화벽 룰 제거(복구)

```powershell
Remove-NetFirewallRule -DisplayName "S4A_BLOCK_TESTNET_443"
```

5. 복구 후 alerts/audit tail 스냅샷 저장

---

### T+16h 체크포인트: Kill Switch 복종

목표: kill_switch=true → 신규 진입 100% 차단 + KILL_BLOCK 알림

```powershell
cd C:\projects\NEXT-TRADE
$path="C:\projects\NEXT-TRADE\metrics\live_obs.jsonl"
$ts = ([int64]((Get-Date -UFormat %s)) * 1000) + (Get-Date).Millisecond
$line = "{\"ts\": $ts, \"risk_level\": \"CRITICAL\", \"kill_switch\": true, \"downgrade_level\": 2, \"reason\": \"S4A_kill_switch_test\", \"trace_id\": \"S4A-KILL-001\", \"recovery_count\": 0 }"
Add-Content -Path $path -Value $line
```

이후:

- `alerts.jsonl`에 KILL_BLOCK 기록 확인
- 신규 ENTRY 시도 BLOCKED 확인
- 스냅샷 저장(1-B)

---

## 3) PASS 판정 기준 (S4-A)

72H 완주의 정의:

1. 재시작 후 상태 복구 + 엔진 생존
2. 네트워크 단절 동안 EXCHANGE_ERROR 기록 + 엔진 생존, 복구 후 정상화
3. kill_switch 주입 후 신규 진입 100% 차단 + KILL_BLOCK 증거
4. `alerts.jsonl / execution_audit.jsonl / runtime_state.json` 증거가 시간순으로 남아 있음

---

## 4) 즉시 Dennis에게 보고할 1줄

```
S4-A START 확정(2026-02-24 15:41:18 KST, PID 6820). T+2h부터 파일 로그 리다이렉트 방식으로 재기동 전환하고, 체크포인트마다 state/alerts/audit 스냅샷을 evidence/phase-s4-pilot에 저장합니다.
```

---

## 결론

- 되돌아가는 게 아니다.
- 지금은 엔진이 도는 상태에서 운영 내성(재시작/망/킬)을 증거로 남기는 단계다.
- T+2h 재시작 때부터 로그 파일 리다이렉트로 전환하면, 이후는 증거가 자동으로 쌓인다.
