"""
next_trade.runtime.__main__

Entry point when running: python -m next_trade.runtime

This ensures the Live S2B engine starts properly with all initialization.
"""

import asyncio
import os
from pathlib import Path

# Engine initialization (replicate the __main__ block from live_s2b_engine.py)

# --------------------------------------------------------------------------
# SSOT: Write engine PID to file (watchdog's SSOT source of truth)
# --------------------------------------------------------------------------
engine_pid = os.getpid()
project_root = Path(__file__).resolve().parents[3]
runtime_dir = project_root / "logs" / "runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)

engine_pid_file = runtime_dir / "engine.pid"
try:
    engine_pid_file.write_text(str(engine_pid), encoding="utf-8")
    print(f"[ENGINE_PID_SSOT] ✅ Engine PID {engine_pid} written to {engine_pid_file}")
except Exception as e:
    print(f"[ENGINE_PID_SSOT] ⚠️  Failed to write engine.pid: {e}")

# Import engine after PID file is written
from .live_s2b_engine import LiveS2BEngine, _start_checkpoint_heartbeat

# Start checkpoint heartbeat daemon thread BEFORE event loop
checkpoint_log = runtime_dir / "checkpoint_log.txt"
_start_checkpoint_heartbeat(str(checkpoint_log), interval_sec=10)

# Get credentials
binance_key = os.getenv("BINANCE_KEY", "")
binance_secret = os.getenv("BINANCE_SECRET", "")

# Create and run engine
engine = LiveS2BEngine(
    project_root=project_root,
    apikey=binance_key,
    secret=binance_secret,
    testnet=True,
)

asyncio.run(engine.run())
