#!/usr/bin/env python3
"""
NEXT-TRADE S5 Runtime Health Watchdog
- Monitors engine process health
- Detects stagnation via heartbeat file
- Auto-restarts with exponential backoff
- Anti-flap safety (max 3 restarts per 10min)
- All events logged to JSONL
"""

import os
import sys
import json
import time
import socket
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import logging

# ============================================================================
# Configuration
# ============================================================================

NEXT_TRADE_DIR = Path("C:\\projects\\NEXT-TRADE")
VENV_PYTHON = NEXT_TRADE_DIR / "venv" / "Scripts" / "python.exe"

# --- SYS CHILD REAPER (PMX) ---
# If any system-python watchdog appears, kill it immediately to enforce runtime purity.
def _reap_system_watchdog_children():
    try:
        result = subprocess.run(
            [
                "wmic", "process", "where",
                "Name='python.exe' and CommandLine like '%watchdog_runtime.py%' and CommandLine like '%Python312%'",
                "get", "ProcessId",
            ],
            capture_output=True, text=True
        )
        lines = [ln.strip() for ln in (result.stdout or "").splitlines() if ln.strip().isdigit()]
        for pid in lines:
            # never kill self
            if str(pid) == str(os.getpid()):
                continue
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True)
    except Exception:
        pass

_reap_system_watchdog_children()
# --- END REAPER ---

# --- MP SPAWN EXECUTABLE ENFORCE (PMX) ---
# Force Windows spawn to use venv python (prevents sys._base_executable -> system python fan-out)
import multiprocessing as _mp
try:
    _mp.set_executable(str(VENV_PYTHON))
except Exception:
    pass
# --- END MP ENFORCE ---

# --- VENV ENFORCEMENT GUARD (PMX) ---
# If watchdog is launched with system Python, immediately re-exec using venv python.
# Prevents mixed-runtime duplicate watchdog/engine/api spawns.
import os as _os
from pathlib import Path as _Path
import sys as _sys

def _ensure_venv_python():
    try:
        venv_py = _Path(VENV_PYTHON).resolve()
        cur_py  = _Path(_sys.executable).resolve()
    except Exception:
        return

    # Avoid infinite respawn loop
    if _os.environ.get("NEXT_TRADE_WD_REEXEC") == "1":
        return

    if cur_py != venv_py:
        env2 = _os.environ.copy()
        env2["NEXT_TRADE_WD_REEXEC"] = "1"
        try:
            subprocess.Popen(
                [str(venv_py), str(_Path(__file__).resolve()), *_sys.argv[1:]],
                cwd=str(NEXT_TRADE_DIR),
                env=env2,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        finally:
            # Exit immediately to prevent system-python watchdog from doing anything.
            raise SystemExit(0)

_ensure_venv_python()
# --- END GUARD ---
ENGINE_MODULE = "next_trade.runtime"
CHECKPOINT_FILE = NEXT_TRADE_DIR / "logs" / "runtime" / "checkpoint_log.txt"
WATCHDOG_LOG = NEXT_TRADE_DIR / "logs" / "runtime" / "watchdog_runtime.log"
WATCHDOG_EVENTS = NEXT_TRADE_DIR / "evidence" / "phase-s5-watchdog" / "watchdog_events.jsonl"
RUNTIME_DIR = NEXT_TRADE_DIR / "logs" / "runtime"
ENGINE_PID_FILE = RUNTIME_DIR / "engine.pid"

# Singleton: port-binding (race-condition-free, auto-released on process exit)
SINGLETON_PORT = 19876

# Backoff sequence (seconds)
BACKOFF_DELAYS = [10, 30, 60]
MAX_RESTART_ATTEMPTS_PER_WINDOW = 3
WINDOW_DURATION = 600  # 10 minutes

# Default thresholds
DEFAULT_CHECK_INTERVAL = 30  # seconds
DEFAULT_CHECKPOINT_THRESHOLD = 120  # seconds

# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(log_file):
    """Configure logging to file."""
    WATCHDOG_LOG.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

logger = logging.getLogger(__name__)

# ============================================================================
# Event Logging
# ============================================================================

def write_event(level: str, action: str, details: Dict[str, Any]):
    """Write event to JSONL log (evidence)."""
    WATCHDOG_EVENTS.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "action": action,
        **details
    }

    with open(WATCHDOG_EVENTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
        f.flush()

# ============================================================================
# Singleton Lock (Phase 3)
# ============================================================================

LOCK_PATH = Path(r"C:\projects\NEXT-TRADE\logs\runtime\watchdog.lock")

def acquire_singleton_lock():
    """Acquire singleton lock via port binding (race-condition-free).

    Returns:
        Bound socket on success, None if another instance is already running.
        The socket must be kept open for the lifetime of the watchdog process.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    try:
        sock.bind(("127.0.0.1", SINGLETON_PORT))
        # Write PID to lock file for observability (best-effort, not for locking)
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCK_PATH.write_text(str(os.getpid()), encoding="utf-8")
        logger.info(f"[SINGLETON] Port lock acquired: 127.0.0.1:{SINGLETON_PORT} PID={os.getpid()}")
        return sock
    except OSError:
        sock.close()
        logger.error(f"[SINGLETON] Port {SINGLETON_PORT} already bound ??another watchdog is running")
        return None

def release_singleton_lock(lock_obj) -> None:
    """Release singleton lock (close socket + remove PID file)."""
    try:
        if lock_obj is not None:
            lock_obj.close()
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
        logger.info("[SINGLETON] Port lock released")
    except Exception as e:
        logger.warning(f"[SINGLETON] Lock release error: {e}")

# ============================================================================
# PID File SSOT
# ============================================================================

def _ensure_runtime_dir() -> None:
    try:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Runtime directory ensured: {RUNTIME_DIR}")
    except Exception as e:
        logger.error(f"Failed to create runtime dir {RUNTIME_DIR}: {e}")


def write_engine_pid(pid: int) -> None:
    """Write engine PID to file (SSOT). This MUST succeed."""
    _ensure_runtime_dir()
    try:
        ENGINE_PID_FILE.write_text(str(int(pid)), encoding="utf-8")
        logger.info(f"[PID_SSOT] Engine PID {pid} written to {ENGINE_PID_FILE}")
    except Exception as e:
        logger.error(f"[PID_SSOT] CRITICAL: Failed to write engine.pid for PID {pid}: {e}")


def read_engine_pid() -> Optional[int]:
    """Read engine PID from file (SSOT)."""
    try:
        if ENGINE_PID_FILE.exists():
            s = ENGINE_PID_FILE.read_text(encoding="utf-8").strip()
            if s:
                pid = int(s)
                logger.debug(f"[PID_SSOT] Read engine PID {pid} from {ENGINE_PID_FILE}")
                return pid
        else:
            logger.debug(f"[PID_SSOT] engine.pid file not found: {ENGINE_PID_FILE}")
    except Exception as e:
        logger.error(f"[PID_SSOT] Failed to read engine.pid: {e}")
    return None


def clear_engine_pid() -> None:
    """Remove engine.pid file."""
    try:
        if ENGINE_PID_FILE.exists():
            ENGINE_PID_FILE.unlink()
            logger.info(f"[PID_SSOT] Cleared engine.pid: {ENGINE_PID_FILE}")
        else:
            logger.debug(f"[PID_SSOT] engine.pid already absent")
    except Exception as e:
        logger.error(f"[PID_SSOT] Failed to clear engine.pid: {e}")


def process_exists_windows(pid: int) -> bool:
    """
    Check PID existence via WMIC (Windows). Avoids psutil dependency.
    """
    try:
        pid = int(pid)
        result = subprocess.run(
            ["wmic", "process", "where", f"ProcessId={pid}", "get", "ProcessId"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        out = (result.stdout or "").strip()
        exists = str(pid) in out
        logger.debug(f"[PROCESS_CHECK] PID {pid} exists: {exists}")
        return exists
    except Exception as e:
        logger.error(f"[PROCESS_CHECK] WMI check failed for PID {pid}: {e}")
        return False

# ============================================================================
# Process Detection
# ============================================================================

def is_engine_alive() -> Optional[int]:
    """
    Returns engine PID if alive, else None.
    SSOT: logs/runtime/engine.pid (priority). Falls back to WMI scan only when PID file is missing/stale.
    """
    # Step 1: Try PID file (SSOT)
    pid = read_engine_pid()
    if pid:
        if process_exists_windows(pid):
            logger.debug(f"[IS_ENGINE_ALIVE] Engine found via PID file: {pid}")
            return pid
        else:
            logger.warning(f"[IS_ENGINE_ALIVE] PID file has stale PID {pid} (process doesn't exist), clearing...")
            clear_engine_pid()
    else:
        logger.debug("[IS_ENGINE_ALIVE] No PID file found, attempting WMI scan...")

    # Step 2: Scan via WMI (fallback)
    try:
        result = subprocess.run(
            [
                "wmic",
                "process",
                "where",
                "Name='python.exe' and CommandLine like '%next_trade.runtime%'",
                "get",
                "ProcessId",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        out = (result.stdout or "")
        pids = []
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                pids.append(int(line))

        if pids:
            found = pids[-1]
            logger.info(f"[IS_ENGINE_ALIVE] Engine found via WMI scan: {found} (writing to PID file)")
            write_engine_pid(found)
            return found
        else:
            logger.warning("[IS_ENGINE_ALIVE] WMI scan found no engine process")
    except Exception as e:
        logger.error(f"[IS_ENGINE_ALIVE] WMI scan failed: {e}")

    logger.warning("[IS_ENGINE_ALIVE] Engine process not alive (PID file missing, WMI scan empty)")
    return None

# ============================================================================
# Checkpoint/Heartbeat Monitoring
# ============================================================================

def is_checkpoint_fresh(checkpoint_path: Path, threshold_sec: int) -> bool:
    """
    Check if checkpoint file was updated recently.
    Returns True if fresh (within threshold), False if stale.
    """
    if not checkpoint_path.exists():
        logger.warning(f"Checkpoint file not found: {checkpoint_path}")
        return False

    mtime = checkpoint_path.stat().st_mtime
    age_sec = time.time() - mtime

    if age_sec <= threshold_sec:
        return True
    else:
        logger.warning(f"Checkpoint stale: {age_sec:.1f}s (threshold: {threshold_sec}s)")
        return False

# ============================================================================
# Engine Control
# ============================================================================

def start_engine() -> Optional[int]:
    """
    Start engine process with proper environment.
    Returns PID if successful, None otherwise.
    """
    logger.info("Starting engine process...")

    # Prepare environment
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(NEXT_TRADE_DIR / "src")
    env["NEXT_TRADE_LIVE_TRADING"] = "1"

    # Setup log files for engine stdout/stderr (CRITICAL: keep file handles OPEN)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    engine_stdout_log = RUNTIME_DIR / "engine_stdout.log"
    engine_stderr_log = RUNTIME_DIR / "engine_stderr.log"

    try:
        # MUST KEEP OPEN: Open files with append mode, keep handles alive
        stdout_f = open(engine_stdout_log, "a", encoding="utf-8", buffering=1)
        stderr_f = open(engine_stderr_log, "a", encoding="utf-8", buffering=1)

        # --- VENV PATH ENFORCE (PMX) ---
        env["PATH"] = str(VENV_PYTHON.parent) + ";" + env.get("PATH", "")
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)

        proc = subprocess.Popen(
            [str(VENV_PYTHON), "-m", "next_trade.runtime.live_s2b_engine"],
            cwd=str(NEXT_TRADE_DIR),
            env=env,
            stdout=stdout_f,
            stderr=stderr_f,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )

        logger.info(f"Engine started: PID {proc.pid}")
        logger.info(f"Engine logs: stdout={engine_stdout_log}, stderr={engine_stderr_log}")
        logger.info(f"[CRITICAL] File handles KEPT OPEN for engine I/O")

        write_engine_pid(proc.pid)
        write_event("INFO", "ENGINE_START", {"pid": proc.pid})
        return proc.pid
    except Exception as e:
        logger.error(f"Failed to start engine: {e}")
        write_event("ERROR", "ENGINE_START_FAIL", {"error": str(e)})
        return None

def stop_engine(pid: int) -> bool:
    """
    Gracefully stop engine, then force kill if needed.
    Returns True if successful.
    """
    logger.info(f"Stopping engine (PID {pid})...")

    try:
        write_event("INFO", "ENGINE_KILL", {"pid": pid})
        # Try graceful stop
        subprocess.run(
            ["taskkill", "/PID", str(pid)],
            capture_output=True,
            timeout=5
        )
        time.sleep(2)

        # Check if still alive, force kill if needed
        proc = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Guard against None stdout (P3 hotfix)
        if str(pid) in (proc.stdout or ""):
            logger.warning(f"Process still alive, force killing...")
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                timeout=5
            )

        logger.info(f"Engine stopped: PID {pid}")
        if read_engine_pid() == pid:
            clear_engine_pid()
        write_event("INFO", "ENGINE_KILL_RESULT", {"pid": pid, "result": "stopped"})
        return True
    except Exception as e:
        logger.error(f"Failed to stop engine: {e}")
        write_event("ERROR", "ENGINE_KILL_FAIL", {"pid": pid, "error": str(e)})
        return False

# ============================================================================
# Anti-Flap Safety
# ============================================================================

class RestartTracker:
    """Track restart attempts to prevent flapping."""

    def __init__(self, max_attempts: int, window_sec: int):
        self.max_attempts = max_attempts
        self.window_sec = window_sec
        self.attempts = []  # List of timestamps
        self.fatal_state = False  # Permanent FATAL flag

    def can_restart(self) -> bool:
        """Check if restart is allowed."""
        # If already in fatal state, don't allow any restarts
        if self.fatal_state:
            return False

        now = time.time()

        # Remove old attempts outside window
        self.attempts = [t for t in self.attempts if now - t < self.window_sec]

        if len(self.attempts) >= self.max_attempts:
            logger.critical(
                f"TOO MANY RESTARTS ({len(self.attempts)} in {self.window_sec}s)"
            )
            write_event("CRITICAL", "FLAP_DETECTED", {
                "attempts": len(self.attempts),
                "window_sec": self.window_sec
            })
            self.fatal_state = True  # Set permanent FATAL flag
            return False

        return True

    def record_attempt(self):
        """Record a restart attempt."""
        self.attempts.append(time.time())
        logger.info(f"Restart recorded: {len(self.attempts)}/{self.max_attempts} in window")

# ============================================================================
# Main Watchdog Loop
# ============================================================================

def main(check_interval: int, checkpoint_threshold: int, lock_fd: int):
    """Main watchdog loop.

    Args:
        check_interval: Seconds between health checks
        checkpoint_threshold: Max seconds before checkpoint considered stale
        lock_fd: Singleton lock file descriptor (for cleanup on exit)
    """
    logger.info("=" * 70)
    logger.info("NEXT-TRADE S5 Runtime Health Watchdog started")
    logger.info(f"Check interval: {check_interval}s")
    logger.info(f"Checkpoint threshold: {checkpoint_threshold}s")
    logger.info("=" * 70)

    restart_tracker = RestartTracker(
        max_attempts=MAX_RESTART_ATTEMPTS_PER_WINDOW,
        window_sec=WINDOW_DURATION
    )

    restart_index = 0  # For backoff selection
    last_restart_time = None

    while True:
        try:
            # Check engine process
            pid = is_engine_alive()

            if pid is None:
                logger.warning("Engine process not found")
                write_event("WARN", "PIDFILE_MISSING", {})

                if restart_tracker.can_restart():
                    if last_restart_time and (time.time() - last_restart_time) > 300:
                        # Reset backoff if 5 minutes have passed
                        restart_index = 0

                    # Apply backoff delay
                    delay = BACKOFF_DELAYS[min(restart_index, len(BACKOFF_DELAYS) - 1)]
                    logger.info(f"Waiting {delay}s before restart (attempt {restart_index + 1})")
                    time.sleep(delay)

                    new_pid = start_engine()
                    if new_pid:
                        restart_tracker.record_attempt()
                        restart_index += 1
                        last_restart_time = time.time()
                        write_event("INFO", "RESTART", {"old_pid": None, "new_pid": new_pid})
                    else:
                        logger.error("Failed to start engine")
                        write_event("ERROR", "RESTART_FAILED", {})
                else:
                    logger.critical("FATAL: Too many restart attempts. Entering idle state.")
                    write_event("CRITICAL", "FATAL_FLAP", {})
                    # Stay in idle, don't attempt restart
                    time.sleep(60)
            else:
                # Engine process exists, check heartbeat
                if is_checkpoint_fresh(CHECKPOINT_FILE, checkpoint_threshold):
                    # Verify process still alive before HEALTH_OK
                    if pid and process_exists_windows(pid):
                        # All good
                        logger.info(f"[HEALTH_OK] Engine healthy: PID {pid} (checkpoint fresh, process verified)")
                        restart_index = 0  # Reset backoff
                        last_restart_time = None
                        write_event("INFO", "HEALTH_OK", {"pid": pid})
                    else:
                        logger.error(f"[HEALTH_OK_FAIL] Checkpoint fresh but PID {pid} process doesn't exist! Listing all engine processes...")
                        # Force re-scan to find true engine PID
                        new_pid = is_engine_alive()
                        if new_pid and new_pid != pid:
                            logger.warning(f"[HEALTH_OK_FAIL] Found different engine PID: {new_pid} (was {pid})")
                            pid = new_pid
                            write_event("WARNING", "PID_MISMATCH_DETECTED", {"old_pid": pid, "new_pid": new_pid})
                        else:
                            logger.critical(f"[HEALTH_OK_FAIL] Engine process truly missing despite checkpoint! Triggering restart...")
                            write_event("CRITICAL", "HEALTH_FAIL", {"reason": "process_missing_checkpoint_fresh", "pid": pid})
                else:
                    # Checkpoint stale - restart
                    logger.warning(f"Checkpoint stale, restarting engine (PID {pid})")

                    if restart_tracker.can_restart():
                        stop_engine(pid)
                        time.sleep(2)

                        delay = BACKOFF_DELAYS[min(restart_index, len(BACKOFF_DELAYS) - 1)]
                        logger.info(f"Waiting {delay}s before restart")
                        time.sleep(delay)

                        new_pid = start_engine()
                        if new_pid:
                            restart_tracker.record_attempt()
                            restart_index += 1
                            last_restart_time = time.time()
                            write_event("INFO", "RESTART", {"old_pid": pid, "new_pid": new_pid})
                    else:
                        logger.critical("FATAL: Too many restart attempts - hard stop")
                        write_event("CRITICAL", "FATAL", {
                            "reason": "anti_flap_threshold",
                            "restart_count": len(restart_tracker.attempts),
                            "window_sec": restart_tracker.window_sec
                        })
                        release_singleton_lock(lock_fd)
                        sys.exit(3)  # FATAL hard stop (Phase 3)

        except KeyboardInterrupt:
            logger.info("Watchdog interrupted by user")
            break
        except Exception as e:
            logger.exception(f"Unexpected error in watchdog loop: {e}")
            write_event("ERROR", "WATCHDOG_ERROR", {"error": str(e)})
            time.sleep(check_interval)

        # Standard check interval
        time.sleep(check_interval)

# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="NEXT-TRADE S5 Runtime Health Watchdog"
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=DEFAULT_CHECK_INTERVAL,
        help=f"Check interval in seconds (default: {DEFAULT_CHECK_INTERVAL})"
    )
    parser.add_argument(
        "--checkpoint-threshold",
        type=int,
        default=DEFAULT_CHECKPOINT_THRESHOLD,
        help=f"Checkpoint staleness threshold in seconds (default: {DEFAULT_CHECKPOINT_THRESHOLD})"
    )

    args = parser.parse_args()

    setup_logging(WATCHDOG_LOG)

    # Acquire singleton lock FIRST (port-binding, race-condition-free)
    lock_obj = acquire_singleton_lock()
    if lock_obj is None:
        write_event("ERROR", "EXIT_ALREADY_RUNNING", {"pid": os.getpid()})
        logger.critical("[SINGLETON] Another watchdog instance is already running")
        sys.exit(2)

    try:
        write_event("INFO", "WATCHDOG_START", {"pid": os.getpid()})
        main(
            check_interval=args.check_interval,
            checkpoint_threshold=args.checkpoint_threshold,
            lock_fd=lock_obj
        )
    except KeyboardInterrupt:
        logger.info("Watchdog interrupted by user")
        write_event("INFO", "WATCHDOG_STOP", {"reason": "keyboard_interrupt"})
    except Exception as e:
        logger.exception(f"Watchdog fatal error: {e}")
        write_event("ERROR", "WATCHDOG_FATAL_ERROR", {"error": str(e)})
    finally:
        release_singleton_lock(lock_obj)
        logger.info("Watchdog shutdown")


