# 📘 NEXT-TRADE MASTER RUNBOOK v1.1

문서번호: `NEXT-TRADE-MASTER-RUNBOOK-001.1`
상태: **PH7C Observation Mode (Design Freeze)**
기준일: 2026-03-04 (KST)
헌법: **MR_ONLY / ENGINE_APPLY_STATUS=DISABLED / Engine-unmodified / Shadow-only**

---

## ⛔ 즉시 중단 트리거 (STOP NOW)

아래 3개 중 **하나라도** 발생하면 **즉시 운영 중단 + 원인 확인**한다.

1. `ENGINE_APPLY_STATUS != DISABLED`
2. `UNKNOWN_RATE_LAST_24H > 5%`
3. `SCHEDULE_LAST_RESULT_* != 0` (corr/guard 등 스케줄 실패)

> 원칙: **자동 조치/자동 적용 금지**. 중단 후 “원인 확인 → 보고 → 승인” 순서로만 처리.

---

# 1️⃣ 용어 고정 (Terminology Lock)

## 1.1 ENGINE_MODE (전략 선택)

- 의미: **엔진이 어떤 전략을 “선택해서 실행하느냐”**
- 현재 고정값:
  - `ENGINE_MODE = MR_ONLY`
- 해석:
  - 엔진은 **Mean Reversion 전략만** 선택/실행한다.

## 1.2 ENGINE_APPLY_STATUS (가중치/전략 적용 잠금)

- 의미: **PH7C/PH7D에서 만든 가중치/스코어링을 실거래 로직에 “적용”할 수 있는지 잠금 상태**
- 현재 고정값:
  - `ENGINE_APPLY_STATUS = DISABLED`
- 해석:
  - PH7C의 결과는 **관측/리포트/경보**에만 사용된다.
  - **실거래 의사결정(진입/수량/차단)에 영향 0**이어야 한다.

---

# 2️⃣ 시스템 아키텍처 지도 (1장)

```text
[ENGINE 8100]
  live_s2b_engine / execution / guardrail
        |
        v
[EVENT + EVIDENCE SSOT]
  logs/runtime + evidence/evergreen/perf
        |
        v
[OBS PIPELINE]
  regression / alert_hits / corr / guard_sim
        |
        v
[UI API 3001]
  /api/ops/ph7c-regression (read-only)
        |
        v
[COMMAND CENTER]
  PH7C card + Last3Days + drift + alert(0/N/A/>0)
        |
        v
[BACKUP + SCHEDULER]
  nexttrade_backup.ps1 / Day3 / Day7 / sha256 / manifest
```

---

# 3️⃣ 엔진 (Trading Engine)

## 역할

실제 거래 실행 (단, 현재는 **MR_ONLY** 고정).

## 현재 운영 상태

```text
ENGINE_MODE=MR_ONLY
ENGINE_APPLY_STATUS=DISABLED
ALGO_COMPLIANCE_STATUS=PASS
```

## 금지

- 엔진/주문 로직 수정
- Apply 활성화
- 실시간 전략 삽입

---

# 4️⃣ 관측 시스템 (Observability / PH7C)

## 목적

- 데이터 품질 검증(UNKNOWN)
- 규칙 안정성(rule drift)
- 스케줄 정상성(corr/guard)
- PH7D 심의 근거 축적

## SSOT 경로

```text
C:\projects\NEXT-TRADE\evidence\evergreen\perf\
```

## 핵심 산출물(예)

- `ph7c_daily_regression_*.txt`
- `PH7C_DESIGN_FREEZE_20260304.txt`
- `PH7C_ALERT_POLICY_20260304.txt`
- `regime_signal_corr_*.txt`
- `mr_guard_sim_*.txt`

---

# 5️⃣ UI (Command Center)

## URL

- `http://localhost:3001/command-center`
- `http://localhost:3001/command-center/events`

## PH7C Card 표시(핵심)

- `UNKNOWN_RATE_LAST_24H`
- `RULES_WITH_NONZERO_WEIGHT`
- `WEIGHT_SUM`
- `ALERT_HITS` (0 / N/A / >0)
- `ENGINE_APPLY_STATUS`
- `Last 3 Days`
- `DRIFT_DETECT`

## UI API (Read-only)

- `/api/ops/ph7c-regression`
  - `available`
  - `values`
  - `history`
  - `alert_file / alert_hits`

---

# 6️⃣ 백업 (Backup)

## 백업 스크립트

- `C:\projects\NEXT-TRADE\tools\ops\nexttrade_backup.ps1`

## Stage

```text
PH7B_FREEZE / PH7C_FREEZE / PH7C_DAY3 / PH7C_DAY7 / PH7D_IMPLANT
```

## 산출물

- `NEXT-TRADE_<STAGE>_<TS>.zip`
- `sha256_<STAGE>_<TS>.txt`
- `BACKUP_MANIFEST_<STAGE>_<TS>.txt`

---

# 7️⃣ 스케줄러 (Scheduler)

## Day3/Day7 백업 작업

- `NEXTTRADE_PH7C_DAY3_BACKUP`
- `NEXTTRADE_PH7C_DAY7_BACKUP`

## 실행 방식(고정)

- `-Command`로 dot-source 후 함수 호출

```powershell
-Command "& { . '$script'; Invoke-NextTradeBackup -Stage PH7C_DAY3 }"
```

---

# 8️⃣ Day3 / Day7 게이트 (숫자화)

## PH7D 검토(심의) 진입 조건 (Day3 기준)

아래를 **3일 연속** 만족해야 “PH7D 검토” 가능.

- `ENGINE_APPLY_STATUS=DISABLED` 유지
- `UNKNOWN_RATE=0 유지` *(실무: UNKNOWN_RATE_LAST_24H=0.00% 유지)*
- `RULES_WITH_NONZERO_WEIGHT >= 1`
- `WEIGHT_SUM <= 0.50`
- `3일 연속 drift 없음` *(UI drift 경보 미발생)*
- `SCHEDULE_LAST_RESULT_* = 0` 유지

## Day7 기준

Day3 조건을 유지하면서 **7일 누적 안정성**을 확인 후,

- PH7D 문서/절차 검토(Apply 금지 유지)
- Safe Implant Runbook 준수 여부만 확인

---

# 9️⃣ 운영 절차(고정 순서)

## 재개(Resume) 절차

1. **PH7C_FREEZE 백업(수동 1회 검증)**
2. Day3/Day7 스케줄 등록
3. 관측 3일 시작
4. Day3/Day7 백업 + 해시/매니페스트 검증
5. PH7D 검토

---

# 🔁 롤백 절차 (5줄 고정)

1. **복구할 ZIP 선택**
2. `sha256_*.txt`와 ZIP의 SHA256 **재검증**
3. 대상 경로에 **압축 해제(덮어쓰기 정책 고정)**
4. 서비스 재기동(UI/필요 시 API) *(실행은 dennis가 터미널에서 직접)*
5. `health` 확인 (`/command-center` 200, `/api/ops/ph7c-regression` 200, 엔진 APPLY=DISABLED 확인)

---

# ✅ Dennis 30초 점검 루틴(최종)

1. `/command-center` 진입
2. PH7C 카드 상단 상태 OK/WARN/CRITICAL
3. 즉시 중단 트리거 3개 체크
4. D0: U/R/W/A 확인
5. Last 3 Days: drift/안정 여부 확인


---
참조 헌법: docs/NEXT-TRADE-CONSTITUTION-001.md

