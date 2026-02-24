# S5 Watchdog Runbook

**Purpose:** Operational guide for starting, monitoring, and troubleshooting the NEXT-TRADE S5 Runtime Watchdog.

**Last Updated:** 2026-02-25
**Status:** ✅ PRODUCTION READY (Phase 0-3 Complete)

---

## 1. Architecture Overview

### Components

- **Watchdog:** `tools/watchdog_runtime.py` — process supervisor with health checks every 30 seconds
- **Engine:** Live S2-B trading engine (`src/next_trade/runtime/live_s2b_engine.py`)
- **Entry Point:** `src/next_trade/runtime/__main__.py` — ensures consistent engine initialization when invoked via `-m next_trade.runtime`
- **PID SSOT:** `logs/runtime/engine.pid` — single source of truth for engine process ID
- **Checkpoint:** `logs/runtime/checkpoint_log.txt` — engine heartbeat (updates every 10 seconds)
- **Events Log:** `evidence/phase-s5-watchdog/watchdog_events.jsonl` — all watchdog actions

### Safety Mechanisms (Phase 0-3)

- **Phase 0:** Singleton lock (`logs/runtime/watchdog.lock`) — prevents multiple watchdog instances
- **Phase 1:** PID SSOT — engine writes own PID to file on startup
- **Phase 2:** Checkpoint heartbeat daemon thread — independent of async event loop
- **Phase 3:** Anti-flapping — max 3 restarts per 600s → FATAL state on violation

---

## 2. Clean Boot Procedure

### Prerequisites

- Python 3.12.8 venv at `C:\projects\NEXT-TRADE\venv`
- Environment variables:
  - `BINANCE_KEY` (optional for testnet)
  - `BINANCE_SECRET` (optional for testnet)

### Commands

```powershell
# Navigate to project root
Set-Location C:\projects\NEXT-TRADE

# Kill any existing Python processes (CAUTION: kills ALL Python processes)
Stop-Process -Name python -Force -ErrorAction SilentlyContinue

# Wait for cleanup
Start-Sleep -Milliseconds 500

# Remove stale runtime files
Remove-Item -Path "logs\runtime\watchdog.lock" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "logs\runtime\engine.pid" -Force -ErrorAction SilentlyContinue

# Start watchdog
& "c:\projects\NEXT-TRADE\venv\Scripts\python.exe" -u tools\watchdog_runtime.py
```

---

## 3. Expected Output (Normal Operation)

### On Startup (first 10 seconds)

```
2026-02-25 00:06:05,442 | INFO | Starting engine process...
2026-02-25 00:06:05,447 | INFO | Engine started: PID 2292
2026-02-25 00:06:05,447 | INFO | Engine logs: stdout=C:\projects\NEXT-TRADE\logs\runtime\engine_stdout.log, stderr=C:\projects\NEXT-TRADE\logs\runtime\engine_stderr.log
2026-02-25 00:06:05,447 | INFO | [CRITICAL] File handles KEPT OPEN for engine I/O
2026-02-25 00:06:05,447 | INFO | [PID_SSOT] Engine PID 2292 written to C:\projects\NEXT-TRADE\logs\runtime\engine.pid
2026-02-25 00:06:05,448 | INFO | Restart recorded: 1/3 in window
```

### Health Check Cycles (every 30 seconds)

```
2026-02-25 00:06:35,556 | INFO | [IS_ENGINE_ALIVE] PID from engine.pid: 2292
2026-02-25 00:06:35,557 | INFO | [IS_ENGINE_ALIVE] Process with PID 2292 exists: True
2026-02-25 00:06:35,558 | INFO | Engine is alive, checkpoint fresh
```

---

## 4. Health Verification Commands

### Check Engine Process

```powershell
# Check if engine PID from file exists
$engine_pid = Get-Content "logs\runtime\engine.pid" -ErrorAction SilentlyContinue
Get-Process python -ErrorAction SilentlyContinue | Where-Object Id -eq $engine_pid
```

**Expected:** Process with matching PID showing memory usage (PM) around 30-40 MB.

### Check Checkpoint Freshness

```powershell
# Show last 3 checkpoint timestamps
Get-Content "logs\runtime\checkpoint_log.txt" | Select-Object -Last 3
```

**Expected:** Unix timestamps updating every ~10 seconds.

### Check Watchdog Events

```powershell
# Show recent watchdog events
Get-Content "evidence\phase-s5-watchdog\watchdog_events.jsonl" | Select-Object -Last 10
```

**Expected:** Repeating `HEALTH_OK` actions with same PID every 30 seconds.

### All-in-One Health Check

```powershell
Write-Host "=== Engine Process ===" -ForegroundColor Cyan
$engine_pid = Get-Content "logs\runtime\engine.pid" -ErrorAction SilentlyContinue
if ($engine_pid) {
    $proc = Get-Process python -ErrorAction SilentlyContinue | Where-Object Id -eq $engine_pid
    if ($proc) {
        Write-Host "✅ Engine PID $engine_pid ALIVE" -ForegroundColor Green
        $proc | Format-Table Id, CPU, PM, Handles
    } else {
        Write-Host "❌ Engine PID $engine_pid DEAD (in file but process not found)" -ForegroundColor Red
    }
} else {
    Write-Host "❌ engine.pid file not found" -ForegroundColor Red
}

Write-Host "`n=== Checkpoint Heartbeat ===" -ForegroundColor Cyan
if (Test-Path "logs\runtime\checkpoint_log.txt") {
    $lines = (Get-Content "logs\runtime\checkpoint_log.txt" | Measure-Object -Line).Lines
    $last_checkpoint = Get-Content "logs\runtime\checkpoint_log.txt" | Select-Object -Last 1
    $checkpoint_age = [int]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - [double]$last_checkpoint)
    Write-Host "Total checkpoints: $lines"
    Write-Host "Last checkpoint: $checkpoint_age seconds ago"
    if ($checkpoint_age -lt 15) {
        Write-Host "✅ Checkpoint is FRESH" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Checkpoint is STALE (>15s)" -ForegroundColor Yellow
    }
} else {
    Write-Host "❌ checkpoint_log.txt not found" -ForegroundColor Red
}

Write-Host "`n=== Watchdog Events (last 5) ===" -ForegroundColor Cyan
Get-Content "evidence\phase-s5-watchdog\watchdog_events.jsonl" -ErrorAction SilentlyContinue | Select-Object -Last 5
```

---

## 5. Troubleshooting

### Issue: "Engine process not found" (30-second death pattern)

**Symptoms:**

- Watchdog logs show `Engine started: PID XXXXX` then 30s later `Engine process not found`
- `engine.pid` file exists but process not running
- No entries in `engine_stdout.log`

**Root Causes:**

1. **Missing `__main__.py` entry point** → Engine's `if __name__ == "__main__"` block never executes
   - **Fix:** Verify `src/next_trade/runtime/__main__.py` exists
   - **Verification:** `Test-Path src\next_trade\runtime\__main__.py` should return `True`

2. **Import errors on engine startup** → Check `engine_stderr.log` for traceback
   - **Fix:** Ensure all dependencies installed: `pip install -r requirements.txt`
   - **Check:** `cat logs\runtime\engine_stderr.log | Select-Object -First 50`

3. **Environment variables missing** → Engine exits if critical config absent
   - **Fix:** Set `BINANCE_KEY` and `BINANCE_SECRET` (optional for testnet)

### Issue: "Another watchdog instance already running"

**Symptoms:**

```
ERROR | [SINGLETON] Already running (lock exists: C:\projects\NEXT-TRADE\logs\runtime\watchdog.lock)
```

**Fix:**

```powershell
# Kill watchdog process
Stop-Process -Name python -Force -ErrorAction SilentlyContinue

# Remove stale lock
Remove-Item -Path "logs\runtime\watchdog.lock" -Force -ErrorAction SilentlyContinue

# Restart
& "c:\projects\NEXT-TRADE\venv\Scripts\python.exe" -u tools\watchdog_runtime.py
```

### Issue: Watchdog enters FATAL state

**Symptoms:**

```
CRITICAL | Anti-flap limit reached: 3 restarts in 600s
CRITICAL | Entering FATAL state, stopping watchdog
```

**Root Cause:** Engine is repeatedly crashing within 10 minutes, triggering anti-flap protection.

**Diagnosis Steps:**

1. Check `logs\runtime\engine_stderr.log` for recurring errors
2. Check `evidence\phase-s5-watchdog\watchdog_events.jsonl` for `RESTART` events pattern
3. Verify Binance testnet connectivity (if applicable)

**Recovery:**

1. Fix underlying issue causing crashes
2. Clean boot (see Section 2)
3. Monitor for at least 10 minutes to confirm stability

### Issue: "RuntimeWarning: 'next_trade.runtime.live_s2b_engine' found in sys.modules"

**Symptoms:**

```
<frozen runpy>:128: RuntimeWarning: 'next_trade.runtime.live_s2b_engine' found in sys.modules after import of package 'next_trade.runtime'
```

**Status:** ⚠️ **KNOWN WARNING (safe to ignore)**

- This warning appears when using `-m next_trade.runtime` invocation with `__main__.py`
- The engine still initializes correctly (PID file created, checkpoint running)
- **No action needed** — warning is cosmetic, does not affect functionality

**Verification:** Check that `engine.pid` and `checkpoint_log.txt` are updating normally.

---

## 6. Stopping the Watchdog

### Graceful Shutdown

```powershell
# Send Ctrl+C to watchdog terminal
# Watchdog will stop engine process and clean up
```

### Force Stop

```powershell
# Kill all Python processes (CAUTION: affects ALL Python processes)
Stop-Process -Name python -Force -ErrorAction SilentlyContinue

# Clean up lock files
Remove-Item -Path "logs\runtime\watchdog.lock" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "logs\runtime\engine.pid" -Force -ErrorAction SilentlyContinue
```

---

## 7. Maintenance

### Log Rotation

Watchdog and engine logs grow over time. Recommended rotation:

```powershell
# Archive current logs
$archive_dir = "logs\archive\$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Force -Path $archive_dir | Out-Null
Move-Item "logs\runtime\watchdog_runtime.log" $archive_dir -Force -ErrorAction SilentlyContinue
Move-Item "logs\runtime\engine_stdout.log" $archive_dir -Force -ErrorAction SilentlyContinue
Move-Item "logs\runtime\engine_stderr.log" $archive_dir -Force -ErrorAction SilentlyContinue

# Restart watchdog to create fresh logs
```

### Events Log Cleanup

```powershell
# Archive events older than 7 days
$cutoff = (Get-Date).AddDays(-7)
Get-Content "evidence\phase-s5-watchdog\watchdog_events.jsonl" |
    Where-Object { [DateTime]::Parse(($_ | ConvertFrom-Json).ts) -gt $cutoff } |
    Set-Content "evidence\phase-s5-watchdog\watchdog_events.jsonl.new"
Move-Item "evidence\phase-s5-watchdog\watchdog_events.jsonl.new" "evidence\phase-s5-watchdog\watchdog_events.jsonl" -Force
```

---

## 8. Performance Baselines

### Healthy Engine Metrics (30+ minutes runtime)

| Metric              | Expected Range        | Measurement                              |
| ------------------- | --------------------- | ---------------------------------------- |
| CPU Usage           | 0.2 - 0.5 CPU-seconds | `(Get-Process python -Id <PID>).CPU`     |
| Memory (PM)         | 30-45 MB              | `(Get-Process python -Id <PID>).PM`      |
| Handles             | 220-240               | `(Get-Process python -Id <PID>).Handles` |
| Checkpoint Age      | < 15 seconds          | Last timestamp in `checkpoint_log.txt`   |
| HEALTH_OK Frequency | Every 30s ± 2s        | `watchdog_events.jsonl`                  |

### Watchdog Restart Budget

- **Normal:** 0-1 restarts per day (transient network issues)
- **Warning:** 2 restarts in 1 hour (investigate logs)
- **Critical:** 3 restarts in 10 minutes → FATAL state (requires manual intervention)

---

## 9. Contact & Escalation

**Maintainer:** Honey (AI Agent)
**Supervisor:** Dennis
**Last Verified:** 2026-02-25
**Evidence Archive:** `evidence/phase-s5-watchdog/_final_20260225_001515/`

**For Issues:**

1. Capture full `watchdog_runtime.log` and `engine_stderr.log`
2. Export last 50 lines of `watchdog_events.jsonl`
3. Include output of health check command (Section 4)
4. Report to Dennis with ticket reference: `PHASE-S5-ENGINE-EXIT-TRIAGE-007`

---

## Appendix: File Locations Reference

| File                                               | Purpose                  | Rotation                |
| -------------------------------------------------- | ------------------------ | ----------------------- |
| `tools/watchdog_runtime.py`                        | Watchdog supervisor code | N/A (source)            |
| `src/next_trade/runtime/__main__.py`               | Engine entry point       | N/A (source)            |
| `src/next_trade/runtime/live_s2b_engine.py`        | Trading engine core      | N/A (source)            |
| `logs/runtime/watchdog.lock`                       | Singleton lock file      | Auto-cleanup on exit    |
| `logs/runtime/engine.pid`                          | Engine process ID (SSOT) | Auto-refresh on restart |
| `logs/runtime/checkpoint_log.txt`                  | Engine heartbeat         | Manual rotation         |
| `logs/runtime/watchdog_runtime.log`                | Watchdog logs            | Manual rotation         |
| `logs/runtime/engine_stdout.log`                   | Engine stdout            | Manual rotation         |
| `logs/runtime/engine_stderr.log`                   | Engine stderr            | Manual rotation         |
| `evidence/phase-s5-watchdog/watchdog_events.jsonl` | Structured events log    | Archive after 7 days    |

---

**End of Runbook**
