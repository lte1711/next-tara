# 📜 NEXT-TRADE CONSTITUTION

문서번호: `NEXT-TRADE-CONSTITUTION-001`
상태: **ACTIVE**
발효: 즉시
역할 고정: Honey(실행), Gemini(검증), Dennis(최종 승인)

## Core Architecture (변경 불가)

```text
Market
  ↓
ENGINE
  ↓
EVENT / LOG
  ↓
EVIDENCE SSOT
  ↓
OBSERVABILITY
  ↓
UI / COMMAND CENTER
  ↓
OPS / BACKUP / RUNBOOK
```

## Hard Rules

- `ENGINE_MODE = MR_ONLY`
- `ENGINE_APPLY_STATUS = DISABLED`
- Engine/주문 로직 무단 변경 금지
- UI/Analysis에서 Engine 직접 제어 금지
- Evidence(`evidence/evergreen/perf`)는 append-only 원칙

## Hard Stop Triggers

- `ENGINE_APPLY_STATUS != DISABLED`
- `UNKNOWN_RATE_LAST_24H > 5%`
- `SCHEDULE_LAST_RESULT_* != 0`

## Governance

- 모든 변경 전: Backup → Hash → Manifest 검증
- 문제 시: ZIP 선택 → SHA 검증 → 복원 → 서비스 재기동 → health 확인
- PH7D SAFE IMPLANT 승인 전까지 Apply 금지

## Operational Principle

- NEXT-TRADE는 `Trading Research + Execution System`
- 개발 흐름: `Data → Evidence → Analysis → Algorithm → Engine`

