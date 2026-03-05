# NEXT-TRADE Runbook

Document ID: `NEXT-TRADE-OPS-EVERGREEN-RUNBOOK-017`  
Status: Operational  
Scope: Daily operations for Evergreen Observation mode

## 1) Start Conditions
All must be true:
- Engine running
- API `127.0.0.1:8100` listening
- `ops/health` is `OK` (or controlled `WARN`)
- `open_orders = 0`
- `positions = 0`

Commands:
```powershell
curl http://127.0.0.1:8100/api/v1/ops/health
curl http://127.0.0.1:8100/api/v1/trading/open_orders
curl http://127.0.0.1:8100/api/v1/trading/positions
```

## 2) 1-Minute Daily Check
```powershell
Get-ChildItem C:\projects\NEXT-TRADE\evidence\evergreen -Filter "run_summary_*.txt" |
Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content

Get-ChildItem C:\projects\NEXT-TRADE\evidence\evergreen -Filter "session_60m_*.txt" |
Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content

Get-ChildItem C:\projects\NEXT-TRADE\evidence\evergreen -Filter "fail_*" |
Sort-Object LastWriteTime -Descending | Select-Object -First 5
```

## 3) Active Schedulers (SSOT)
- `NEXTTRADE_EVG_OBS_15M`
- `NEXTTRADE_EVG_REPORT_60M`
- `NEXTTRADE_EVG_SUMMARY_24H`
- `NEXTTRADE_EVG_SNAPSHOT_ON_FAIL`
- `NEXTTRADE_EVG_PERF_AGG_60M`
- `NEXTTRADE_EVG_PERF_DAILY`
- `NEXTTRADE_EVG_PERF_WEEKLY`
- `NEXTTRADE_EVG_QUALITY_DAILY`
- `NEXTTRADE_EVG_ALGO_AUDIT_60M`

## 4) Immediate Attention Conditions
- `health=CRITICAL`
- New `fail_*` snapshot file
- Rapid `SL` increase
- Rapid `BLOCKED` increase
- No `ENTRY/EXIT` for prolonged period
- `ACCOUNT_FAIL` occurrence

## 5) Evidence Locations
- Evergreen evidence: `evidence/evergreen/`
- Perf reports: `evidence/evergreen/perf/`
- Event SSOT: `logs/runtime/profitmax_v1_events.jsonl`
- Trade SSOT: `evidence/evergreen/perf_trades.jsonl`

## 6) Incident Response (Minimal)
1. Capture `ops/health`, `open_orders`, `positions`.
2. Check latest `fail_*`, `algo_audit_*`, `quality_assessment_*`.
3. If `CRITICAL` due to checkpoint freshness:
```powershell
schtasks /Run /TN NEXTTRADE_PMX003R_WATCHDOG_2M
schtasks /Run /TN NEXTTRADE_PMX003R_SNAPSHOT_10M
```
4. Re-check `ops/health`.

## 7) Do / Don’t
Do:
- Use SSOT files for decisions.
- Keep scheduler lock + atomic write behavior intact.

Do not:
- Modify strategy entry/exit logic during observation-only phase.
- Bypass risk guards.
- Introduce alternate metrics sources without approval.

## 8) Exit Criteria
Session or run termination events:
- `RUN_END`
- `STOPPED_EARLY`
- `ACCOUNT_FAIL`
- `MAX_CONSECUTIVE_SL`
