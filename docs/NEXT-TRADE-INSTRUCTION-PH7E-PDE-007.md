# NEXT-TRADE-INSTRUCTION-PH7E-PDE-007

효력: 즉시  
목적: Gate-E1 자동 실행 검증 + Pattern Discovery Engine 착수 준비

## 0) 헌법 고정
- ENGINE_MODE=MR_ONLY
- ENGINE_APPLY_STATUS=DISABLED
- Engine-unmodified
- Shadow-only

## 1) Honey 실행 지시
### STEP 1 — Gate-E1 자동 실행 검증
- 실행 시점: 2026-03-05 22:10 KST 이후
- 확인 항목:
  - LastResult=0
  - PH7E_HEALTH_STATUS=PASS
  - ENGINE_APPLY_STATUS=DISABLED
- 증거 파일:
  - evidence/analysis/logs/ph7e_framework_YYYYMMDD.log
  - evidence/analysis/ph7e_daily_health.txt
  - evidence/analysis/schtasks_NEXTTRADE_PH7E_FRAMEWORK_DAILY_YYYYMMDD.txt

### STEP 2 — 로그 보존
- 폴더: evidence/analysis/logs/
- 파일: ph7e_framework_YYYYMMDD.log

### STEP 3 — Pattern Catalog 준비
- 생성 파일: evidence/analysis/pattern_catalog_v1.json

## 2) Gemini 검증 지시
- 보고: PH7E_GATE_E1_VERDICT
- 검증 항목:
  - schedule execution success
  - health PASS
  - engine isolation
  - output integrity

## 3) Hard Stop
- ENGINE_APPLY_STATUS != DISABLED
- LastResult != 0
- Health FAIL
- Output missing

## 4) Dennis 운영 체크
1. schtasks LastResult=0
2. ph7e_daily_health.txt STATUS=PASS
3. ENGINE_APPLY_STATUS=DISABLED

