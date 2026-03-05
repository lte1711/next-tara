# [NEXT-TRADE-PH7E-OPS-003] PH7E Quant Framework 운영 고정 + 일 1회 자동화

문서번호: `NEXT-TRADE-PH7E-OPS-003`
효력: 즉시
대상: Honey(실행) / Gemini(검증) / Dennis(승인)

## A. 헌법 고정 (절대 준수)
- ENGINE_MODE=MR_ONLY
- ENGINE_APPLY_STATUS=DISABLED
- Engine-unmodified / Shadow-only

## B. AS-IS 확정
- PH7E 모듈 4종 + runner 생성 완료
- 1회 실행 성공
- 산출물 4종 생성
- validation=PASS
- implant_queue=status=pending_dennis
- weight_sum=0.0351 (<=0.50)

## C. Gate-B0 (필수): 자동화 전 백업
백업/해시/매니페스트 PASS 전 스케줄 등록 금지.

필수 포함:
- src/next_trade/algorithm/*
- tools/ops/run_algorithm_framework.ps1
- evidence/analysis/*.json
- docs/NEXT-TRADE-CONSTITUTION-001.md

## D. Gate-E1: PH7E 일 1회 자동 생성
수동 1회:
```powershell
cd C:\projects\NEXT-TRADE
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\ops\run_algorithm_framework.ps1
```

일 1회 스케줄(권장 22:10 KST), -Command 고정:
```powershell
$ErrorActionPreference="Stop"
$repo="C:\projects\NEXT-TRADE"
$runner="$repo\tools\ops\run_algorithm_framework.ps1"
$logDir="$repo\evidence\analysis\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$ts=(Get-Date -Format "yyyyMMdd")
$log="$logDir\ph7e_framework_$ts.log"
$action=New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"& { Set-Location '$repo'; . '$runner' 2>&1 | Tee-Object -FilePath '$log' }`""
$trigger=New-ScheduledTaskTrigger -Daily -At 22:10
Register-ScheduledTask -TaskName "NEXTTRADE_PH7E_FRAMEWORK_DAILY" -Action $action -Trigger $trigger -RunLevel Highest -Force
```

성공 기준:
- LastResult=0
- logs/ph7e_framework_YYYYMMDD.log 생성
- evidence/analysis 산출물 4종 mtime 증가

## E. Gate-E2: 산출물 계약(Contract) 고정
아래 키 변경/삭제 금지(추가만 허용):
1) mined_patterns.json: version, stamp, total_trades, patterns[], rules, source_files[]
2) shadow_strategy_table.json: version, stamp, weight_sum, weight_cap, total_cap, rules[]
3) strategy_validation_report.json: version, stamp, status, metrics, notes
4) implant_queue.json: version, stamp, candidates[], status=pending_dennis

## F. Gate-E3: Hard Stop 감시(보고 전용)
아래는 즉시 중단/긴급 보고:
- ENGINE_APPLY_STATUS != DISABLED
- UNKNOWN_RATE_LAST_24H > 5%
- SCHEDULE_LAST_RESULT_* != 0
- PH7E_DAILY_TASK_LAST_RESULT != 0
- PH7E_VALIDATION_STATUS != PASS

일 1회 상태 파일:
- evidence/analysis/ph7e_daily_health_YYYYMMDD.txt

## G. Gemini 검증 포맷
```text
VAL_PH7E_CONSTITUTION=PASS/FAIL
VAL_PH7E_ENGINE_IMPACT=NONE (required)
VAL_PH7E_OUTPUT_CONTRACT=PASS/FAIL
VAL_PH7E_VALIDATION_STATUS=PASS/FAIL
VAL_PH7E_OVERFIT_GUARD=PASS/INFO
RECOMMENDATION=HOLD/PROCEED_TO_PH7D_REVIEW
TOP_EVIDENCE=
```

## H. Dennis 승인 범위
Dennis 승인 없이는 절대 금지:
- Engine apply
- Strategy 변경
- Guardrail 변경

PH7E는 후보 생성 + 검증 + 대기열까지만 수행.
