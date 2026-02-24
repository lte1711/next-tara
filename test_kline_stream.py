#!/usr/bin/env python3
"""
Simple binance WebSocket kline test
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from src.next_trade.runtime.binance_ws_feed import BinanceKlineWSFeed

async def test_stream():
    feed = BinanceKlineWSFeed("BTCUSDT", "4h")
    print("[Test] Starting kline stream...")

    count = 0
    try:
        async for kline in feed.stream_closes():
            count += 1
            print(f"[Test] Received kline #{count}")
            print(f"  Close: {kline.close}, Time: {kline.close_time_ms}")
            if count >= 1:
                print("[Test] Got 1 kline, exiting")
                break
    except KeyboardInterrupt:
        print("[Test] Interrupted")
    except Exception as e:
        print(f"[Test] Error: {e}")

    print(f"[Test] Total received: {count}")

if __name__ == "__main__":
    try:
        asyncio.run(asyncio.wait_for(test_stream(), timeout=30))
    except asyncio.TimeoutError:
        print("[Test] Timeout after 30s")
    print("[Test] Done")
