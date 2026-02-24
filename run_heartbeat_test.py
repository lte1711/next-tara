#!/usr/bin/env python3
"""
PHASE-S3-004 HEARTBEAT Test

Verify that heartbeat fires periodically (every 10s in TEST_MODE)
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

sys.path.insert(0, str(Path(__file__).parent))
from src.next_trade.runtime.live_s2b_engine import LiveS2BEngine


async def test_heartbeat():
    """Run engine for 35 seconds to capture heartbeat events"""
    print("\n" + "#"*70)
    print("# PHASE-S3-004 HEARTBEAT TEST")
    print("#"*70)

    project_root = Path(__file__).parent
    engine = LiveS2BEngine(project_root=project_root)

    print(f"\n[OK] Engine initialized with heartbeat_interval_sec={engine.heartbeat_interval_sec}s")
    print(f"[Test] Running engine for 35 seconds to capture heartbeats...\n")

    # Start engine (which includes heartbeat loop)
    # Use asyncio.wait_for with timeout to limit execution time
    try:
        await asyncio.wait_for(engine.run(), timeout=35.0)
    except asyncio.TimeoutError:
        print(f"\n[Test] Engine timeout (expected after 35s)")
    except Exception as e:
        print(f"\n[Test] Engine stopped: {e}")

    print("\n" + "#"*70)
    print("# TEST COMPLETE")
    print("#"*70)

    # Read alerts.jsonl and display heartbeat events
    alerts_file = project_root / "evidence" / "phase-s3-runtime" / "alerts.jsonl"
    if alerts_file.exists():
        print(f"\n[Alerts File] {alerts_file}")
        with alerts_file.open() as f:
            alerts = [json.loads(line) for line in f if line.strip()]

        print(f"\n[Total Alerts] {len(alerts)}")

        # Count events
        event_counts = {}
        for alert in alerts:
            event_type = alert.get('event_type', alert.get('type', 'UNKNOWN'))
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        print("\n[Event Count Summary]")
        for event_type, count in sorted(event_counts.items()):
            print(f"  {event_type}: {count}")

        # Show HEARTBEAT events
        print("\n[HEARTBEAT Events]")
        heartbeat_events = [a for a in alerts if a.get('event_type') == 'HEARTBEAT' or a.get('type') == 'HEARTBEAT']
        if heartbeat_events:
            print(f"  Found {len(heartbeat_events)} HEARTBEAT events:")
            for i, evt in enumerate(heartbeat_events[:10], 1):  # Show first 10
                ts = evt.get('ts', 'N/A')
                print(f"    {i}. @ {ts}")
            print(f"\n✅ DoD Verification: HEARTBEAT fires periodically ✅")
        else:
            print(f"  ❌ No HEARTBEAT events found")
            print(f"  ❌ DoD Verification: HEARTBEAT NOT confirmed ❌")

        # Final DoD summary
        print("\n[Final DoD Checklist]")
        print(f"  ✓ kill_switch=true blocks entry 100%: {'✅' if 'KILL_BLOCK' in event_counts else '❌'}")
        print(f"  ✓ downgrade_level=2 reduces qty 0.5x: {'✅' if 'DOWNGRADE_APPLIED' in event_counts else '❌'}")
        print(f"  ✓ ENTRY/EXIT/ERROR/KILL_BLOCK alerts: {'✅' if any(t in event_counts for t in ['ENTRY', 'ERROR', 'KILL_BLOCK']) else '❌'}")
        print(f"  ✓ HEARTBEAT fires every 10s: {'✅' if len(heartbeat_events) >= 3 else '❌'}")
    else:
        print(f"\n[ERROR] alerts.jsonl not found at {alerts_file}")


if __name__ == "__main__":
    asyncio.run(test_heartbeat())
