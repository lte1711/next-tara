# S7 Ops Dashboard — Deployment & Validation Guide

**Phase:** S7-OPS-RUNTIME-001
**Status:** Implementation Complete
**Date:** 2026-02-25

---

## 🎯 Implementation Summary

### Backend (NEXT-TRADE)

**New API Endpoints:**

1. `GET /api/ops/runtime-health` — Real-time watchdog + engine health metrics
2. `GET /api/ops/runtime-events?limit=50` — Recent runtime events timeline

**Dependencies Added:**

- `psutil>=5.9.0` (for process validation)

**Files Modified:**

- `src/next_trade/api/app.py` — Added ops endpoints
- `requirements.txt` — Added psutil

---

### Frontend (evergreen-ops-ui)

**New Page:**

- `/ops/runtime` — Full Command Center dashboard

**New Components:**

- `src/components/runtime/HealthPanel.tsx` — System health status panel
- `src/components/runtime/CheckpointCard.tsx` — Checkpoint heartbeat monitor
- `src/components/runtime/RuntimeTimeline.tsx` — Event timeline with filters

**Files Created:**

- `src/app/ops/runtime/page.tsx`
- `src/components/runtime/HealthPanel.tsx`
- `src/components/runtime/CheckpointCard.tsx`
- `src/components/runtime/RuntimeTimeline.tsx`

---

## 🚀 Deployment Steps

### Step 1: Install Backend Dependencies

```powershell
cd C:\projects\NEXT-TRADE
& venv\Scripts\pip.exe install psutil
```

### Step 2: Restart Backend API Server (Port 8100)

```powershell
cd C:\projects\NEXT-TRADE

# Stop existing API server (if running)
Get-Process python -ErrorAction SilentlyContinue |
   Where-Object { $_.CommandLine -match "uvicorn.*next_trade.api.app" } |
   Stop-Process -Force

# Start API server
$env:PYTHONPATH="C:\projects\NEXT-TRADE\src"
$env:NEXT_TRADE_OPS_TOKEN="dev-ops-token-change-me"
& venv\Scripts\python.exe -m uvicorn next_trade.api.app:app --host 127.0.0.1 --port 8100 --log-level info
```

### Step 3: Start UI Development Server (Port 3001)

```powershell
cd C:\projects\evergreen-ops-ui
$env:NEXT_TELEMETRY_DISABLED="1"
npm run dev -- -p 3001
```

### Step 4: Access Dashboard

Open browser to:

````
http://localhost:3001/ops/runtime

### Step 5: Configure UI API Base URL

Create or update `C:\projects\evergreen-ops-ui\.env.local`:

```ini
NEXT_PUBLIC_API_URL=http://127.0.0.1:8100
````

````

---

## ✅ DoD (Definition of Done) Checklist

### 🟢 Health Panel

- [ ] Overall LED status (OK/WARN/CRITICAL) displays correctly
- [ ] Engine PID shown with ALIVE/DEAD indicator
- [ ] Task State shows current scheduler status
- [ ] Restart Count displays recent restart events
- [ ] Flap detection alert appears when triggered

### ⏱ Checkpoint Card

- [ ] Checkpoint age updates every 2 seconds
- [ ] Color transitions: Fresh (green) / Stale (yellow) / Expired (red)
- [ ] Threshold values displayed correctly
- [ ] Last HEALTH_OK timestamp shown

### 📈 Runtime Timeline

- [ ] Events load from API (last 50 events)
- [ ] Level filter works (INFO/WARN/ERROR/CRITICAL)
- [ ] Action filter dropdown populated with unique actions
- [ ] Event icons display correctly
- [ ] Timestamp formatting correct
- [ ] PID details shown for relevant events
- [ ] Timeline updates every 5 seconds

### 🔄 Live Updates

- [ ] Health panel refreshes every 2 seconds
- [ ] Timeline refreshes every 5 seconds
- [ ] "Live" indicator animates
- [ ] Last update timestamp shows current time

### 🎨 UI/UX

- [ ] Responsive layout works on desktop (1920x1080)
- [ ] Loading state shows spinner
- [ ] Error state shows connection error with retry button
- [ ] Sticky header remains at top during scroll
- [ ] Color coding consistent across all components

---

## 🧪 Manual Validation Tests

### Test 1: Basic Health Display

1. Ensure watchdog and engine are running
2. Open `/ops/runtime`
3. Verify:
   - Overall status shows "OK" (green)
   - Engine PID matches `logs\runtime\engine.pid`
   - Task State shows "Running"
   - Checkpoint age < 15s (FRESH)

**Pass Criteria:** All 4 items display correctly

---

### Test 2: Live Updates

1. Open `/ops/runtime`
2. Note current checkpoint age
3. Wait 10 seconds
4. Verify:
   - Checkpoint age increases
   - New HEALTH_OK events appear in timeline
   - "Last Update" timestamp refreshes

**Pass Criteria:** UI updates without page refresh

---

### Test 3: Engine Kill → Recovery Display

1. Open `/ops/runtime` in browser
2. In PowerShell: `Stop-Process -Id (Get-Content C:\projects\NEXT-TRADE\logs\runtime\engine.pid) -Force`
3. Watch dashboard for 60 seconds
4. Verify:
   - Overall status changes to CRITICAL (red)
   - Engine status shows "DEAD"
   - Timeline shows PIDFILE_MISSING event
   - Timeline shows ENGINE_START event (~30s later)
   - Overall status returns to OK
   - Restart count increases by 1

**Pass Criteria:** Dashboard reflects recovery in real-time

---

### Test 4: Timeline Filters

1. Open `/ops/runtime`
2. Set Level filter to "ERROR"
3. Verify: Only ERROR/CRITICAL events shown
4. Set Action filter to "HEALTH_OK"
5. Verify: Only HEALTH_OK events shown
6. Click "Reset Filters"
7. Verify: All events shown again

**Pass Criteria:** Filters work correctly

---

### Test 5: Flap Detection Display

(This requires triggering anti-flap — skip if not needed now)

1. Cause multiple rapid engine kills (3+ times in 10 minutes)
2. Open `/ops/runtime`
3. Verify:
   - Red alert box appears: "Anti-Flap Triggered"
   - Restart count shows high number
   - Flap detected status true

**Pass Criteria:** Flap alert displays correctly

---

## 📊 Expected Dashboard Appearance

### Normal State (OK)

- 🟢 Overall LED: Green "OK"
- Engine: ALIVE (green dot)
- Task: Running (blue badge)
- Checkpoint: < 15s FRESH (green)
- Restart Count: 0 (green)
- Timeline: Mostly HEALTH_OK (blue badges)

### Warning State (STALE Checkpoint)

- 🟡 Overall LED: Yellow "WARN"
- Engine: ALIVE (green dot)
- Checkpoint: 15-60s STALE (yellow)
- Timeline: May show checkpoint age increasing

### Critical State (Engine Dead)

- 🔴 Overall LED: Red "CRITICAL"
- Engine: DEAD (red dot)
- Checkpoint: > 60s EXPIRED (red)
- Timeline: PIDFILE_MISSING → ENGINE_START pattern

---

## 🔥 Troubleshooting

### Issue: Dashboard shows "Connection Error"

**Cause:** Backend API not running or CORS issue

**Fix:**

```powershell
# Check if API is running
curl http://127.0.0.1:8100/api/ops/runtime-health

# If not, start it
cd C:\projects\NEXT-TRADE
& venv\Scripts\python.exe -m uvicorn next_trade.api.app:app --host 127.0.0.1 --port 8100 --log-level info
````

### Issue: Dashboard shows all null values

**Cause:** Watchdog not running or file paths incorrect

**Fix:**

```powershell
# Verify files exist
Test-Path C:\projects\NEXT-TRADE\logs\runtime\engine.pid
Test-Path C:\projects\NEXT-TRADE\logs\runtime\checkpoint_log.txt
Test-Path C:\projects\NEXT-TRADE\evidence\phase-s5-watchdog\watchdog_events.jsonl

# Start watchdog if needed
cd C:\projects\NEXT-TRADE
schtasks /Run /TN "NEXTTRADE_WATCHDOG"
```

### Issue: Timeline shows no events

**Cause:** Events file empty or not accessible

**Fix:**

```powershell
# Check events file
Get-Content C:\projects\NEXT-TRADE\evidence\phase-s5-watchdog\watchdog_events.jsonl -Tail 10

# Verify watchdog is logging
Get-Content C:\projects\NEXT-TRADE\logs\runtime\watchdog_runtime.log -Tail 20
```

---

## 🎯 Strategic Value

With S7 Complete:

- ✅ Real-time operational visibility
- ✅ No CLI needed for status checks
- ✅ Ready for 72h Shadow Run monitoring
- ✅ Investor demo ready ("operational control panel")
- ✅ Foundation for S8 Stress Testing UI

---

## 📌 Next Steps After S7

1. **Validation:** Complete DoD checklist above
2. **Evidence:** Screenshot dashboard in OK/WARN/CRITICAL states
3. **Documentation:** Update S7 completion report
4. **Commit:** Git commit S7 deliverables
5. **Advance:** Proceed to S8 (Failure Stress Testing) or Shadow Run 72h

---

**End of Deployment Guide**
