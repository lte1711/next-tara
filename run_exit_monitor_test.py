#!/usr/bin/env python3
"""
PHASE-S3-003 Exit Monitor Smoke Test

Purpose:
- Create forced LONG/SHORT position in TEST_MODE
- Stream mark_price ticks to trigger SL/TP
- Verify immediate exit (no kline_close wait)
- Confirm position state changed to FLAT

DoD Evidence:
1. "[LiveS2B] TEST: forced LONG entry=... sl=... tp=..."
2. "[LiveS2B] mark_tick price=..." (multiple ticks)
3. "[LiveS2B] EXIT_TRIGGER hit=SL|TP price=... threshold=..."
4. "[DryRun.Execution] CLOSE order_id=..."
5. "[LiveS2B] State saved" with status FLAT
"""
import asyncio
import os
import sys
from pathlib import Path

# Set environment BEFORE importing engine
os.environ["DRY_RUN"] = "1"
os.environ["TEST_MODE"] = "1"
os.environ["SYMBOL"] = "BTCUSDT"
os.environ["S2B_FORCE_POSITION"] = "LONG"  # Force LONG position for testing

# Import after env setup
sys.path.insert(0, str(Path(__file__).parent))
from src.next_trade.runtime.live_s2b_engine import LiveS2BEngine


async def main():
    """Run exit monitor smoke test"""
    project_root = Path(__file__).parent

    print("="*70)
    print("PHASE-S3-003 Exit Monitor Smoke Test")
    print("="*70)
    print(f"Project: {project_root}")
    print(f"DRY_RUN: {os.getenv('DRY_RUN')}")
    print(f"TEST_MODE: {os.getenv('TEST_MODE')}")
    print(f"FORCE_POSITION: {os.getenv('S2B_FORCE_POSITION')}")
    print(f"SYMBOL: {os.getenv('SYMBOL')}")
    print("="*70)
    print()

    # Create engine instance
    engine = LiveS2BEngine(
        project_root=project_root,
        apikey="",
        secret="",
        testnet=True,
    )

    print(f"✓ Engine initialized")
    print(f"  Position after init: {engine.position.state.value}")
    print(f"  Entry: {engine.position.entry_price}, SL: {engine.position.sl_price}, TP: {engine.position.tp_price}")
    print()

    # Run with timeout
    # TEST_MODE will:
    # 1. Force LONG position immediately
    # 2. Return empty kline_close stream (no entries)
    # 3. Yield 5 fake mark_price ticks: [100, 99, 98, 97, 110]
    #    - First 3 tick prices (100, 99, 98) should not trigger
    #    - 4th tick (97.0) = SL price, so should trigger SL exit
    # 4. Remaining streams should complete quickly

    try:
        print("[Test] Starting engine with TEST_MODE...")
        await asyncio.wait_for(engine.run(), timeout=15.0)
    except asyncio.TimeoutError:
        print("\n[Test] Timeout after 15 seconds (this is OK for smoke test)")
    except KeyboardInterrupt:
        print("\n[Test] Interrupted by user")
    except Exception as e:
        print(f"\n[Test] Engine stopped: {e}")
    finally:
        print()
        print("="*70)
        print("Final State:")
        print(f"  Position: {engine.position.state.value}")
        print(f"  Trades executed: {engine.trades_executed}")
        print(f"  PnL realized: {engine.pnl_realized:.4f}")
        print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
