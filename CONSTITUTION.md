# NEXT-TRADE Constitution

Document ID: `NEXT-TRADE-CONSTITUTION-001`  
Status: `PERMANENT LOCK`  
Owner: `Dennis`  
Effective: Immediate / Permanent

## 1) Purpose
- Ensure system stability, algorithm integrity, data trust, operational consistency, and security.
- This is the highest-priority project policy.

## 2) Fixed Architecture
```
Binance Futures
  -> Exchange Adapter
  -> Strategy Engine (PMX003R)
  -> Event SSOT
  -> Perf SSOT
  -> Metrics / Reports
```

## 3) SSOT Rules
- Event SSOT: `logs/runtime/profitmax_v1_events.jsonl`
- Trade SSOT: `evidence/evergreen/perf_trades.jsonl`
- Metrics SSOT: performance metrics must use `perf_trades.jsonl` as primary source.

## 4) Engine Loop (Do Not Reorder)
```
while engine_running:
  read_market_state
  evaluate_strategy
  risk_guard_check
  execute_orders
  emit_event
```

## 5) Position State Safety
```
NO_POSITION -> ENTERING -> IN_POSITION -> (TP|SL|EXIT|KILL)
```
- On close, required state:
  - `open_orders = 0`
  - `positions = 0`

## 6) Risk Guard Policy
- Required guard checks before execution:
  - Minimum edge
  - Cooldown
  - Max consecutive SL
  - Account failure
  - System health
- Guard failure must emit blocking event.

## 7) Metrics Formula Policy
- `winrate = wins / trades`
- `expectancy = P(win)*avg_win - P(loss)*avg_loss`
- `profit_factor = gross_profit / gross_loss`
- `max_drawdown = equity peak-to-trough`
- Calculations are based on Trade SSOT.

## 8) Credential Policy
- `.env` load entrypoint is `app.py`.
- Credential resolution function is `src/next_trade/config/creds.py`.
- Routes must not directly load `.env` (except explicit emergency fallback flag).

## 9) Scheduler Policy
- Scheduled scripts must use lock files.
- Output writes must be atomic.

## 10) Evergreen Automation
- `obs_15m`
- `report_60m`
- `run_summary_24h`
- `snapshot_on_fail`
- `perf_aggregate`

## 11) Team Roles
- Steering: Baeksul
- Execution: Honey
- Verification: Gemini
- Operations: Dennis

## 12) Change Control (Constitution Approval Required)
- Engine loop
- SSOT locations
- Metrics formulas
- Risk guard core logic
- API credential structure

## 13) Compliance Rules
- No speculation
- Log-based decisions
- SSOT-based analysis

## 14) Violations
- Ignoring SSOT
- Ad-hoc metrics formulas
- Engine structural changes without approval
- Guard bypass
- Unapproved direct dotenv loading in routes

## 15) Mandatory Reference
- All work must check this file before implementation or operations.
