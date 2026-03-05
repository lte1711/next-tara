# PH7D Safe Implant Runbook

## Purpose
Define a conservative, rollback-first path to move from `shadow-only` scoring into limited live influence.

## Hard Constraints
- Keep `MR_ONLY` until Dennis approval.
- No direct engine apply without explicit gate pass.
- Preserve `ALGO_COMPLIANCE_STATUS=PASS`.

## Pre-Apply Gates
1. Fresh backup zip + SHA256 recorded.
2. `UNKNOWN_RATE_LAST_24H <= 5%`.
3. `RULES_WITH_NONZERO_WEIGHT >= 1`.
4. `MAX_WEIGHT <= 0.10`, `WEIGHT_SUM <= 0.50`.
5. `SCHEDULE_LAST_RESULT_CORR=0` and `SCHEDULE_LAST_RESULT_GUARD=0`.

## Implant Sequence (Conservative)
1. Phase D1: Observe-only shadow rules for 3-7 days (no execution impact).
2. Phase D2: Enable one low-risk guard candidate at weight `0.01` equivalent.
3. Phase D3: Hold for at least 24h; verify no compliance regressions.
4. Phase D4: Increase one step at a time (max single-step delta `+0.01`).
5. Phase D5: Re-run daily regression after each change before next step.

## Immediate Rollback Triggers
- Any `ALGO_COMPLIANCE_STATUS != PASS`.
- Scheduler failures (`LastResult != 0`) on critical reporting tasks.
- Drawdown spike beyond policy threshold.
- Guard over-block signs or unexpected trade starvation.

## Rollback Procedure
1. Disable new implant flag(s) immediately.
2. Restore last approved config snapshot.
3. Re-run baseline reports:
   - `regime_signal_corr`
   - `mr_guard_sim`
   - `ph7c_daily_regression`
4. Log incident and freeze further changes.

## Stop Conditions
- If two consecutive days show degraded replay separation (`LOW/HIGH` inversion), stop escalation.
- If unknown rate rises above threshold without clear data-source reason, stop escalation.

## Approval Rules
- Any apply action requires Dennis explicit approval.
- Without approval, remain strictly `shadow-only`.

