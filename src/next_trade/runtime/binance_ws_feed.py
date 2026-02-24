"""
Binance Futures WebSocket Data Feed (4H kline closes)

Streams 4H kline close events from Binance Futures.
Handles reconnection with exponential backoff.
Supports test mode for quick smoke testing.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import AsyncGenerator

try:
    import websockets
except ImportError:
    raise ImportError("Install websockets: pip install websockets")


@dataclass
class KlineClose:
    """4H candle close event"""
    symbol: str
    interval: str
    close_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class BinanceKlineWSFeed:
    """WebSocket feed for Binance Futures kline closes"""

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "4h",
        ws_base: str = "wss://fstream.binance.com",
        test_mode: bool = False,
    ):
        """
        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            interval: Timeframe (e.g., 4h, 1h, 15m)
            ws_base: WebSocket base URL
            test_mode: If True, return fake kline_close after 3s instead of connecting
        """
        self.symbol = symbol.lower()
        self.interval = interval
        self.ws_base = ws_base.rstrip("/")
        self.url = f"{self.ws_base}/ws/{self.symbol}@kline_{self.interval}"
        self.last_event_ts = 0
        self.test_mode = test_mode

    async def stream_closes(self) -> AsyncGenerator[KlineClose, None]:
        """
        Yield kline close events indefinitely with reconnection

        Filters for candle closes (x=true) only.
        Auto-reconnects on network errors with exponential backoff.
        In test_mode, yields a single fake kline_close after 3s.
        """
        if self.test_mode:
            # Test mode: yield a single fake kline after 3 seconds
            print(f"[BinanceWSFeed] TEST_MODE: Will yield fake kline_close after 3s")
            await asyncio.sleep(3)

            current_ts_ms = int(time.time() * 1000)
            fake_close_price = 42857.50  # Fake BTC price

            yield KlineClose(
                symbol="BTCUSDT",
                interval="4h",
                close_time_ms=current_ts_ms,
                open=42800.0,
                high=42900.0,
                low=42700.0,
                close=fake_close_price,
                volume=1000.0,
            )
            print(f"[BinanceWSFeed] TEST_MODE: Fake kline_close yielded, exiting")
            return

        backoff = 1

        while True:
            try:
                async with websockets.connect(
                    self.url,
                    ping_interval=20,
                    ping_timeout=20,
                ) as ws:
                    backoff = 1
                    print(f"[BinanceWSFeed] Connected to {self.symbol}@{self.interval}")

                    async for raw_msg in ws:
                        try:
                            msg = json.loads(raw_msg)
                            k = msg.get("k", {})

                            # Only process closed candles
                            if not k.get("x"):
                                continue

                            self.last_event_ts = int(k["T"])

                            yield KlineClose(
                                symbol=k["s"],
                                interval=k["i"],
                                close_time_ms=int(k["T"]),
                                open=float(k["o"]),
                                high=float(k["h"]),
                                low=float(k["l"]),
                                close=float(k["c"]),
                                volume=float(k["v"]),
                            )
                        except (json.JSONDecodeError, KeyError, ValueError) as e:
                            print(f"[BinanceWSFeed] Parse error: {e}")
                            continue

            except asyncio.CancelledError:
                print("[BinanceWSFeed] Feed cancelled")
                raise
            except Exception as e:
                print(f"[BinanceWSFeed] Connection error: {e}, reconnecting in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
