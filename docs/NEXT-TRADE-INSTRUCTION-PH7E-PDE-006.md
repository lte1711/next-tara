# NEXT-TRADE-INSTRUCTION-PH7E-PDE-006

발신: 총괄(백설)
대상: Honey(실행), Gemini(검증)
효력: 즉시
상태: 헌법 준수 필수

## 0) 헌법 고정 (변경 금지)
- ENGINE_MODE=MR_ONLY
- ENGINE_APPLY_STATUS=DISABLED
- Engine-unmodified
- Shadow-only

## 1) 목표
### 1-A. PH7E Daily 자동화 첫 트리거 Gate
D+1(2026-03-05 22:10 KST) 실행 결과로 아래를 증거화:
- SCHEDULE_LAST_RESULT=0
- PH7E_HEALTH_STATUS=PASS
- 산출물 최신 갱신(analysis 출력물)

### 1-B. Pattern Discovery Engine(PDE) v1 착수
- patterns 6 -> 60+ 확장 기반 카탈로그 구축
- 엔진 영향 0, evidence/analysis 출력 전용

## 2) Honey 실행 지시
### Gate-E1: Daily Task D+1 실트리거 검증
증거 파일:
- evidence/analysis/logs/ph7e_framework_YYYYMMDD.log
- evidence/analysis/ph7e_daily_health.txt
- evidence/analysis/ph7e_daily_health.json
- evidence/analysis/schtasks_NEXTTRADE_PH7E_FRAMEWORK_DAILY_YYYYMMDD.txt

검증 커맨드:
```powershell
schtasks /Query /TN "NEXTTRADE_PH7E_FRAMEWORK_DAILY" /V /FO LIST
```

Gate 통과 조건:
- SCHEDULE_LAST_RESULT=0
- PH7E_HEALTH_STATUS=PASS
- ENGINE_APPLY_STATUS=DISABLED

### Gate-PDE0: Pattern Discovery Engine v1
출력 SSOT:
- evidence/analysis/pattern_catalog_v1.json
- evidence/analysis/pattern_catalog_v1.txt

필수 스키마:
```json
{
  "pattern_id": "PDE_V1_xxx",
  "dimension": ["trend","volatility","time","liquidity","spread","volume"],
  "bucket": {"trend":"UP","volatility":"LOW","session":"ASIA"},
  "n": 0,
  "expectancy": 0.0,
  "pf": 0.0,
  "winrate": 0.0,
  "source": "evidence/analysis/mined_patterns_v2.json",
  "eligibility": {"n_rule": "n>=30", "pass": false},
  "note": ""
}
```

구현 권장:
- src/next_trade/algorithm/pattern_discovery_engine_v1.py
- tools/ops/run_pattern_discovery.ps1

스모크:
```powershell
cd C:\projects\NEXT-TRADE
python -c "from next_trade.algorithm.pattern_discovery_engine_v1 import run; run()"
```

## 3) Gemini 검증 지시
### Gate-E1
- LastResult==0
- Health PASS
- Engine Apply Disabled
- Output files exist/recent

### Gate-PDE0
- schema 준수
- pattern_id 중복 없음
- dimension/bucket/eligibility 누락 없음
- shadow-only, engine 영향 0

## 4) Hard Stop
- ENGINE_APPLY_STATUS != DISABLED
- UNKNOWN_RATE_LAST_24H > 5%
- SCHEDULE_LAST_RESULT != 0 (실행 후)
- Health FAIL

## 5) 팀 보고 포맷
### Honey
```text
DATE_KST=
PH7E_DAILY_TRIGGER=YES
SCHEDULE_LAST_RESULT=
PH7E_HEALTH_STATUS=
ENGINE_APPLY_STATUS=DISABLED
PATTERNS_V2_COUNT=
CATALOG_V1_COUNT=
TOP3_PATTERN_IDS=
```

### Gemini
```text
VAL_DAILY_AUTOMATION=PASS/FAIL
VAL_PDE_SCHEMA=PASS/FAIL
RISK_NOTES=
NEXT_STEP=
```
