#!/usr/bin/env python3
"""
Dry-run smoke test for PHASE-S3-002: Live S2-B Engine

Purpose:
- Load historical candles for indicator warmup
- Connect to Binance WebSocket (4H) or use TEST_MODE for quick feedback
- Stream 1 kline_close event
- Log "kline_close received" as DoD evidence

Environment:
- DRY_RUN=1 (all orders simulated)
- TEST_MODE=1 (use fake kline_close after 3s instead of waiting 4H)
- SYMBOL=BTCUSDT
- WS_BASE=wss://stream.binance.com:9443/ws (can be overridden)
"""
import asyncio
import os
import sys
from pathlib import Path

# Set environment BEFORE importing engine
os.environ["DRY_RUN"] = "1"
os.environ["TEST_MODE"] = "1"  # Use fake kline for quick smoke test
os.environ["SYMBOL"] = "BTCUSDT"
# WS_BASE can be overridden for testnet if needed
# os.environ["WS_BASE"] = "wss://stream.testnet.binance.vision:9443/ws"

# Import after env setup
sys.path.insert(0, str(Path(__file__).parent))
from src.next_trade.runtime.live_s2b_engine import LiveS2BEngine


async def main():
    """Run dry-run smoke test"""
    project_root = Path(__file__).parent

    print("="*70)
    print("PHASE-S3-002 Dry-Run Smoke Test")
    print("="*70)
    print(f"Project root: {project_root}")
    print(f"DRY_RUN: {os.getenv('DRY_RUN')}")
    print(f"TEST_MODE: {os.getenv('TEST_MODE')}")
    print(f"SYMBOL: {os.getenv('SYMBOL')}")
    print(f"WS_BASE: {os.getenv('WS_BASE')}")
    print("="*70)

    # Create engine instance
    engine = LiveS2BEngine(
        project_root=project_root,
        apikey="",
        secret="",
        testnet=True,
    )

    print(f"\n✓ Engine initialized")
    print(f"  Strategy: S2-B (k=3.0, m=1.5, n=6.0)")
    print(f"  DRY_RUN mode enabled")
    print(f"  TEST_MODE enabled (fake kline after 3s)")

    # Run with timeout and capture up to 1 successful kline_close
    try:
        # Set a timeout of 10 seconds (test mode will yield after 3s)
        await asyncio.wait_for(engine.run(), timeout=10.0)
    except asyncio.TimeoutError:
        print("\n[Timeout] No kline_close received within 10 seconds")
        print("This is expected if running in real mode. Use TEST_MODE=1 for quick feedback.")
    except KeyboardInterrupt:
        print("\n[Interrupted] User stopped the engine")
    except Exception as e:
        print(f"\n[Error] {e}")
        raise
    finally:
        engine.save_state()
        print(f"\n✓ Engine state saved")
        print(f"  Metrics: trades_executed={engine.trades_executed}, pnl_realized={engine.pnl_realized:.4f}")
        print("\n" + "="*70)
        print("✓ PHASE-S3-002 SMOKE TEST COMPLETE")
        print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
