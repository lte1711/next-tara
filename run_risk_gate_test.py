#!/usr/bin/env python3
"""
PHASE-S3-004 Risk Gate + Alert Test

Purpose:
- Verify kill_switch blocks NEW entries
- Verify downgrade_level=2 reduces qty to 0.5x
- Confirm ENTRY/EXIT/KILL_BLOCK/DOWNGRADE alerts in alerts.jsonl
- Confirm HEARTBEAT fires every 10s in TEST_MODE

DoD Evidence:
1. "[LiveS2B] BLOCKED: kill_switch=true" in log
2. "[LiveS2B] DOWNGRADE: level=2 qty_multiplier=0.5" in log
3. alerts.jsonl contains KILL_BLOCK, DOWNGRADE_APPLIED events
4. HEARTBEAT alert fires periodically
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Set environment BEFORE importing engine
os.environ["DRY_RUN"] = "1"
os.environ["TEST_MODE"] = "1"
os.environ["SYMBOL"] = "BTCUSDT"
os.environ["S2B_FORCE_POSITION"] = ""  # Start FLAT (no forced position)

sys.path.insert(0, str(Path(__file__).parent))
from src.next_trade.runtime.live_s2b_engine import LiveS2BEngine


async def scenario_1_kill_switch(engine: LiveS2BEngine):
    """
    Scenario 1: kill_switch blocks entry

    Expected:
    - [LiveS2B] BLOCKED: kill_switch=true
    - alerts.jsonl: KILL_BLOCK event
    """
    print("\n" + "="*70)
    print("SCENARIO 1: Kill Switch Blocks Entry")
    print("="*70)

    # Prepare metrics/live_obs.jsonl with kill_switch
    obs_dir = Path(__file__).parent / "metrics"
    obs_dir.mkdir(exist_ok=True)
    obs_file = obs_dir / "live_obs.jsonl"

    # Write kill_switch=true
    with obs_file.open("w") as f:
        f.write(json.dumps({"kill_switch": True, "downgrade_level": 0, "ts": int(time.time() * 1000)}) + "\n")

    print(f"[OK] Written metrics/live_obs.jsonl with kill_switch=true")

    # Force a signal that would normally trigger entry
    print("[Test] Attempting LONG entry with kill_switch=true...")
    await engine.execute_trade("long")

    print("[Test] Entry should have been blocked. Check log for '[LiveS2B] BLOCKED'")


async def scenario_2_downgrade(engine: LiveS2BEngine):
    """
    Scenario 2: downgrade_level=2 reduces qty

    Expected:
    - [LiveS2B] DOWNGRADE: level=2 qty_multiplier=0.5
    - alerts.jsonl: DOWNGRADE_APPLIED event
    """
    print("\n" + "="*70)
    print("SCENARIO 2: Downgrade Reduces Qty")
    print("="*70)

    # Prepare metrics/live_obs.jsonl with downgrade_level=2
    obs_dir = Path(__file__).parent / "metrics"
    obs_file = obs_dir / "live_obs.jsonl"

    # Write downgrade_level=2, kill_switch=false
    with obs_file.open("w") as f:
        f.write(json.dumps({"kill_switch": False, "downgrade_level": 2, "ts": int(time.time() * 1000)}) + "\n")

    # IMPORTANT: Clear risk cache so fresh read happens
    engine.risk.last_snap = None
    engine.risk.last_read_ts = 0

    # Inject candle data for execute_trade (it requires historical candles)
    if not engine.candles:
        engine.candles = [
            {
                "open_time": i * 3600000,
                "open": 100.0 + i * 0.1,
                "high": 100.5 + i * 0.1,
                "low": 99.5 + i * 0.1,
                "close": 100.0 + i * 0.1,
                "volume": 1000.0,
                "close_time": (i + 1) * 3600000,
            }
            for i in range(100)
        ]

    print(f"[OK] Written metrics/live_obs.jsonl with downgrade_level=2")
    print(f"[OK] Cleared risk cache for fresh read")

    # Force entry signal
    print("[Test] Attempting LONG entry with downgrade_level=2...")
    await engine.execute_trade("long")

    print("[Test] Entry should have been applied with 0.5x qty. Check log for '[LiveS2B] DOWNGRADE'")


async def main():
    print("\n" + "#"*70)
    print("# PHASE-S3-004 RISK GATE TEST")
    print("#"*70)

    project_root = Path(__file__).parent
    engine = LiveS2BEngine(project_root=project_root)

    # Scenario 1: kill_switch blocks entry
    await scenario_1_kill_switch(engine)

    # Explicit wait for cache expiry (5 seconds) + small buffer
    print("\n[Test] Waiting 6 seconds for risk cache to expire...")
    await asyncio.sleep(6)

    # Scenario 2: downgrade_level reduces qty
    await scenario_2_downgrade(engine)

    # Let heartbeat fire multiple times (3 cycles at 10s interval = ~35s total)
    print("\n[Test] Letting engine run for 35 seconds to capture heartbeats...")
    await asyncio.sleep(35)

    print("\n" + "#"*70)
    print("# TEST COMPLETE")
    print("#"*70)

    # Read alerts.jsonl and display detailed report
    alerts_file = Path(__file__).parent / "evidence" / "phase-s3-runtime" / "alerts.jsonl"
    if alerts_file.exists():
        print(f"\n[Alerts File] {alerts_file}")
        with alerts_file.open() as f:
            alerts = [json.loads(line) for line in f if line.strip()]

        print(f"\n[DoD Validation Report]")
        print(f"[Total Alerts] {len(alerts)}\n")

        # Categorize by event type
        event_counts = {}
        for alert in alerts:
            event_type = alert.get('event_type', 'UNKNOWN')
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        print("[Event Count Summary]")
        for event_type, count in sorted(event_counts.items()):
            print(f"  {event_type}: {count}")

        print("\n[Detailed Alert Log]")
        for i, alert in enumerate(alerts, 1):
            ts_formatted = alert.get('ts', 'N/A')
            print(f"{i}. [{alert.get('event_type')}] {alert.get('symbol')} @ {ts_formatted}")
            data = alert.get('data', {})
            if isinstance(data, dict):
                for key, val in data.items():
                    print(f"     {key}: {val}")
            else:
                print(f"     {data}")

        # DoD checklist
        print("\n[DoD Validation Checklist]")
        print(f"✓ kill_switch blocks entry (KILL_BLOCK event): {'✅ YES' if 'KILL_BLOCK' in event_counts else '❌ NO'}")
        print(f"✓ downgrade_level reduces qty (DOWNGRADE_APPLIED event): {'✅ YES' if 'DOWNGRADE_APPLIED' in event_counts else '❌ NO'}")
        print(f"✓ ENTRY alert generated: {'✅ YES' if 'ENTRY' in event_counts else '❌ NO'}")
        print(f"✓ EXIT alert generated: {'✅ YES' if 'EXIT' in event_counts else '❌ NO'}")
        print(f"✓ ERROR alert generated: {'✅ YES' if 'ERROR' in event_counts else '❌ NO'}")
        print(f"✓ HEARTBEAT fires periodically: {'✅ YES ({} events)'.format(event_counts.get('HEARTBEAT', 0)) if 'HEARTBEAT' in event_counts else '❌ NO'}")
    else:
        print(f"\n[ERROR] alerts.jsonl not found at {alerts_file}")


if __name__ == "__main__":
    asyncio.run(main())
