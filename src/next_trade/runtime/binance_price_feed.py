"""
Binance Futures Mark Price WebSocket Feed

Streams real-time mark price ticks (1s resolution) for position monitoring.
Used for real-time SL/TP exit triggers (faster than kline close).

Supports test_mode for development (yields fake price sequence then exits).
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
class MarkPriceTick:
    """Mark price tick at 1s resolution"""
    symbol: str
    ts_ms: int
    price: float


class BinanceMarkPriceWSFeed:
    """WebSocket feed for Binance Futures mark price ticks"""

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        ws_base: str = "wss://fstream.binance.com",
        interval: str = "1s",
        test_mode: bool = False,
    ):
        """
        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            ws_base: WebSocket base URL
            interval: Mark price interval (1s or 3s)
            test_mode: If True, yield fake price sequence then exit
        """
        self.symbol = symbol.lower()
        self.ws_base = ws_base.rstrip("/")
        self.interval = interval
        self.test_mode = test_mode
        self.url = f"{self.ws_base}/ws/{self.symbol}@markPrice@{self.interval}"
        self.last_tick_ts = 0

    async def stream(self) -> AsyncGenerator[MarkPriceTick, None]:
        """
        Yield mark price ticks indefinitely with reconnection

        In test_mode, yields a fixed sequence of prices then exits:
        - sequence = [100.0, 99.0, 98.0, 97.0, 110.0]
        - useful for testing SL/TP triggers
        """
        if self.test_mode:
            # Test mode: yield a sequence of prices with 0.1s delay
            # Sequence designed to hit SL on downside and TP on upside
            print(f"[BinanceMarkPriceWSFeed] TEST_MODE: price sequence stream")

            test_prices = [100.0, 99.0, 98.0, 97.0, 110.0]
            base_ts = int(time.time() * 1000)

            for i, price in enumerate(test_prices):
                ts_ms = base_ts + (i * 1000)
                yield MarkPriceTick(
                    symbol=self.symbol.upper(),
                    ts_ms=ts_ms,
                    price=float(price),
                )
                print(f"[BinanceMarkPriceWSFeed] TEST: price={price} ts={ts_ms}")
                await asyncio.sleep(0.1)

            print(f"[BinanceMarkPriceWSFeed] TEST_MODE: sequence complete, exiting")
            return

        # Production mode: connect to real WebSocket
        backoff = 1

        while True:
            try:
                async with websockets.connect(
                    self.url,
                    ping_interval=20,
                    ping_timeout=20,
                ) as ws:
                    backoff = 1
                    print(f"[BinanceMarkPriceWSFeed] Connected to {self.symbol}@markPrice@{self.interval}")

                    async for raw_msg in ws:
                        try:
                            msg = json.loads(raw_msg)

                            # Parse mark price tick
                            # msg keys: E(eventTime), s(symbol), p(markPrice), i(fundingTime)
                            self.last_tick_ts = int(msg["E"])

                            yield MarkPriceTick(
                                symbol=msg["s"],
                                ts_ms=int(msg["E"]),
                                price=float(msg["p"]),
                            )
                        except (json.JSONDecodeError, KeyError, ValueError) as e:
                            print(f"[BinanceMarkPriceWSFeed] Parse error: {e}")
                            continue

            except asyncio.CancelledError:
                print("[BinanceMarkPriceWSFeed] Feed cancelled")
                raise
            except Exception as e:
                print(f"[BinanceMarkPriceWSFeed] Connection error: {e}, reconnecting in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
