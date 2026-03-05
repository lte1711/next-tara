# RUNBOOK Command Center

## Scope
- Operational console: `http://localhost:3001/command-center`
- Contract API base: `http://127.0.0.1:8100`
- Runtime mix gate: `tools/ops/verify_runtime_mix_v2.ps1`

## Startup Order
1. Start API 8100 (`next_trade.api.app`)
```powershell
powershell -ExecutionPolicy Bypass -File C:\projects\NEXT-TRADE\tools\honey_reports\start_api_8100.ps1 -Port 8100 -KillExisting
```
2. Verify contract endpoints are healthy
```powershell
curl http://127.0.0.1:8100/api/v1/ops/health
curl "http://127.0.0.1:8100/api/v1/trading/orders?limit=5"
curl http://127.0.0.1:8100/api/v1/ledger/pnl
curl http://127.0.0.1:8100/api/profitmax/status
```
3. (Optional for session ops) Start PMX 60m runner
```powershell
cd C:\projects\NEXT-TRADE
.\venv\Scripts\python.exe tools\ops\profitmax_v1_runner.py --session-hours 1
```
4. Start UI (safe mode only)
```powershell
cd C:\projects\NEXT-TRADE-UI
npm run dev:safe
```

## 30s Health Check
- Browser opens `http://localhost:3001/command-center`
- No contract error in Command Center
- Contract API 4 endpoints return `200`

## PMX 60m Observation
1. Start collector
```powershell
cd C:\projects\NEXT-TRADE
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\ops\pmx_obs_auto_collect.ps1
```
2. Evidence outputs
- `evidence\pmx\runtime_mix_gate_*.txt`
- `evidence\pmx\session_mid_15m_*.txt`
- `evidence\pmx\session_end_60m_*.txt`

## 1-Min Incident Checklist
1. Runtime mix gate
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\projects\NEXT-TRADE\tools\ops\verify_runtime_mix_v2.ps1
```
2. API 8100 health and contract check
```powershell
curl http://127.0.0.1:8100/api/v1/ops/health
curl "http://127.0.0.1:8100/api/v1/trading/orders?limit=5"
curl http://127.0.0.1:8100/api/v1/ledger/pnl
curl http://127.0.0.1:8100/api/profitmax/status
```
3. UI safe restart (if needed)
```powershell
cd C:\projects\NEXT-TRADE-UI
npm run dev:safe
```

## Operational Locks
- Use `npm run dev:safe` only for operations.
- Keep `NEXT_PUBLIC_CONTRACT_BASE=http://127.0.0.1:8100` in `NEXT-TRADE-UI/.env.local`.
- Run cleanup (`tools/ops/cc_cleanup_v1.ps1`) only as periodic maintenance, not during active sessions.
