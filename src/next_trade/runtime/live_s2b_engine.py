"""
Live S2-B Strategy Engine (Real-time 4H execution)

Approved Strategy:
- Strategy: s2_atr_breakout
- TF: 4H
- k=3.0, m=1.5, n=6.0
- Cost: 4bps + 1bps

Architecture:
- Backtest strategy logic reused 100%
- State machine (FLAT / LONG_ACTIVE / SHORT_ACTIVE)
- WebSocket for live 4H candle closure
- Order adapter for execution
- Risk guardrails integration
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from ..backtest.strategies.s2_atr_breakout import S2AtrBreakoutStrategy
from .binance_ws_feed import BinanceKlineWSFeed, KlineClose
from .binance_price_feed import BinanceMarkPriceWSFeed, MarkPriceTick
from .execution_dryrun import DryRunExecutionAdapter
from .execution_binance_testnet import BinanceTestnetAdapter
from .risk_snapshot import RiskSnapshotProvider
from .alerting import AlertManager, FileAlertSink, SlackWebhookSink


class PositionState(Enum):
    """Position state machine"""
    FLAT = "flat"
    LONG_ACTIVE = "long_active"
    SHORT_ACTIVE = "short_active"


@dataclass
class Position:
    """Active position state"""
    state: PositionState
    entry_price: float | None = None
    sl_price: float | None = None
    tp_price: float | None = None
    position_size: float | None = None
    entry_time: int | None = None
    side: str | None = None  # "long" or "short"


class LiveS2BEngine:
    """
    Real-time S2-B Strategy Engine (4H)

    Requires:
    - Historical candles for indicator warmup
    - WebSocket connection for live 4H closes
    - Order adapter for execution (Binance Futures)
    """

    def __init__(
        self,
        project_root: Path,
        apikey: str = "",
        secret: str = "",
        testnet: bool = True,
    ):
        self.project_root = Path(project_root)
        self.apikey = apikey
        self.secret = secret
        self.testnet = testnet

        # Strategy configuration (S2-B APPROVED)
        self.strategy = S2AtrBreakoutStrategy(k=3.0, m=1.5, n=6.0)

        # Read environment overrides
        self.symbol = os.getenv("SYMBOL", "BTCUSDT")
        self.tf = "4h"
        self.notional = 100.0
        self.fee_bps = 4.0
        self.slippage_bps = 1.0

        # WebSocket and executor configuration
        self.dry_run = os.getenv("DRY_RUN", "0").lower() in ("1", "true")
        self.test_mode = os.getenv("TEST_MODE", "0").lower() in ("1", "true")
        self.ws_base = os.getenv("WS_BASE", "wss://stream.binance.com:9443/ws")

        # Initialize WebSocket feed and executor
        self.ws_feed = BinanceKlineWSFeed(symbol=self.symbol, interval="4h", ws_base=self.ws_base, test_mode=self.test_mode)
        self.price_feed = BinanceMarkPriceWSFeed(symbol=self.symbol, ws_base=self.ws_base, test_mode=self.test_mode)

        # Executor selection with Two-Man Rule
        self.executor = self._select_executor()

        # Risk & Alert systems
        self.risk = RiskSnapshotProvider(obs_file=project_root / "metrics" / "live_obs.jsonl")
        sinks = [FileAlertSink(path=project_root / "evidence" / "phase-s3-runtime" / "alerts.jsonl")]
        # Add Slack sink if webhook configured
        sinks.append(SlackWebhookSink())
        self.alert = AlertManager(sinks=sinks)

        # Heartbeat configuration
        self.heartbeat_interval_sec = 10 if self.test_mode else 3600  # 10s test, 60min prod
        self.last_heartbeat_ts = time.time()

        # State machine
        self.position = Position(state=PositionState.FLAT)
        self._last_exit_ts = 0.0

        # Candle history (for indicator calculation)
        self.candles: list[dict[str, Any]] = []
        self.indicators: dict[str, list[float | None]] = {}

        # Metrics tracking
        self.trades_executed = 0
        self.pnl_realized = 0.0
        self.state_file = project_root / "var" / "runtime_state.json"

        # TEST_MODE: Force initial position for exit testing
        force_pos = os.getenv("S2B_FORCE_POSITION", "").upper()
        if self.test_mode and force_pos in ("LONG", "SHORT"):
            self._force_test_position(force_pos)

    def _select_executor(self):
        """
        Select execution adapter with Two-Man Rule enforcement

        Two-Man Rule (절대 규칙):
        - NEXT_TRADE_LIVE_TRADING=1
        - DENNIS_APPROVED_TOKEN == NEXT_TRADE_APPROVAL_TOKEN

        Only when both conditions true: use BinanceTestnetAdapter
        Otherwise: fallback to DryRunExecutionAdapter
        """
        live_trading = os.getenv("NEXT_TRADE_LIVE_TRADING", "0") == "1"
        dennis_token = os.getenv("DENNIS_APPROVED_TOKEN", "")
        approval_token = os.getenv("NEXT_TRADE_APPROVAL_TOKEN", "")

        # Check Two-Man Rule
        two_man_ok = live_trading and (dennis_token == approval_token) and dennis_token

        print(f"\n[LiveS2B.Executor] Two-Man Rule Check:")
        print(f"  NEXT_TRADE_LIVE_TRADING={live_trading}")
        print(f"  DENNIS_APPROVED_TOKEN={'***' if dennis_token else '(empty)'}")
        print(f"  NEXT_TRADE_APPROVAL_TOKEN={'***' if approval_token else '(empty)'}")
        print(f"  Token match: {dennis_token == approval_token}")
        print(f"  → Two-Man Rule OK: {two_man_ok}")

        if two_man_ok:
            print(f"  ✅ Using BinanceTestnetAdapter (REAL TESTNET ORDERS)")
            return BinanceTestnetAdapter(project_root=self.project_root)
        else:
            print(f"  ℹ️  Fallback: DryRunExecutionAdapter (SIMULATED)")
            return DryRunExecutionAdapter()

    async def run(self) -> None:
        """Main async loop: kline_close signal + mark_price exit monitoring + heartbeat"""
        try:
            await self._load_historical_candles()

            # Run kline, mark_price, and heartbeat streams in parallel
            await asyncio.gather(
                self._run_websocket_loop(),
                self._market_price_loop(),
                self._heartbeat_loop(),
            )
        except KeyboardInterrupt:
            print("[LiveS2B] Shutdown signal received")
            self.save_state()
        except asyncio.CancelledError:
            print("[LiveS2B] Tasks cancelled")
            self.save_state()
        except Exception as e:
            print(f"[LiveS2B] Fatal error: {e}")
            raise

    async def _run_websocket_loop_compat(self) -> None:
        """Compatibility wrapper for old interface - to be removed"""
        await self._run_websocket_loop()

    async def _load_historical_candles(self) -> None:
        """Load past month of 4H candles for indicator warmup"""
        print("[LiveS2B] Loading historical candles...")

        # Attempt to restore from last saved state
        self.load_state()

        # TODO: Fetch from Binance REST API if not loaded
        # Need ~50+ 4H candles for ATR(14) + SMA(20) warmup
        # Use: load_or_download_klines(tf="4h", days=30)

        if len(self.candles) < 50:
            print("[LiveS2B] WARNING: Insufficient historical data (<50 candles)")

    async def _run_websocket_loop(self) -> None:
        """
        Connect to Binance WebSocket and listen for 4H candles

        Streams 4h@kline_closed events and calls on_kline_close() for each.
        """
        print(f"[LiveS2B] Starting WebSocket listener for {self.symbol} 4H candles...")
        print(f"[LiveS2B] DRY_RUN={self.dry_run} | WS_BASE={self.ws_base}")

        try:
            async for kline_close in self.ws_feed.stream_closes():
                await self.on_kline_close(kline_close)
        except Exception as e:
            print(f"[LiveS2B] WebSocket stream error: {e}")
            raise

    async def _market_price_loop(self) -> None:
        """
        Continuous mark price stream for real-time SL/TP exit monitoring

        Independent of kline_close timing - triggers immediately on price movement.
        Runs in parallel with _run_websocket_loop.
        """
        print(f"[LiveS2B] Starting mark price monitor...")

        try:
            async for tick in self.price_feed.stream():
                await self.on_mark_tick(tick)
        except Exception as e:
            print(f"[LiveS2B] Mark price stream error: {e}")
            raise

    async def _heartbeat_loop(self) -> None:
        """
        Periodic heartbeat for monitoring engine health

        Sends HEARTBEAT alert every heartbeat_interval_sec (10s in TEST_MODE, 60min in prod).
        Useful for detecting stale processes.
        """
        print(f"[LiveS2B] Starting heartbeat loop (interval={self.heartbeat_interval_sec}s)...")

        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval_sec)

                await self.alert.send(
                    event_type="HEARTBEAT",
                    symbol=self.symbol,
                    payload={
                        "position": self.position.state.value,
                        "trades": self.trades_executed,
                        "pnl": self.pnl_realized,
                    },
                )
            except Exception as e:
                print(f"[LiveS2B] Heartbeat error: {e}")
                # Continue heartbeat even on error

    async def on_mark_tick(self, tick: MarkPriceTick) -> None:
        """
        Process mark price tick for real-time exit triggers

        Only performs exit check when position is ACTIVE.
        Skips SL/TP check if FLAT to minimize overhead.
        """
        # Skip if no active position
        if self.position.state == PositionState.FLAT:
            return

        price = tick.price
        sl = self.position.sl_price
        tp = self.position.tp_price
        side = self.position.side

        if sl is None or tp is None:
            return

        exit_reason = None
        exit_price = None

        # Check SL/TP conditions immediately on price tick
        if side == "long":
            if price <= sl:
                exit_price = sl
                exit_reason = "SL"
            elif price >= tp:
                exit_price = tp
                exit_reason = "TP"
        else:  # short
            if price >= sl:
                exit_price = sl
                exit_reason = "SL"
            elif price <= tp:
                exit_price = tp
                exit_reason = "TP"

        if exit_reason:
            print(f"[LiveS2B] EXIT_TRIGGER hit={exit_reason} price={price:.2f} threshold={exit_price:.2f}")
            await self._close_position(exit_price, exit_reason)

    def _force_test_position(self, side: str) -> None:
        """
        TEST_MODE: Create fake position for exit testing

        Used to test SL/TP triggers without waiting for real signal entry.
        Injected when S2B_FORCE_POSITION env var is "LONG" or "SHORT".
        """
        # Normalize case
        side_lower = side.lower()

        # Use dummy values for testing
        entry_price = 100.0
        if side_lower == "long":
            sl_price = 97.0  # SL = entry - 3
            tp_price = 110.0  # TP = entry + 10
        else:  # "short"
            sl_price = 103.0  # SL = entry + 3 (short)
            tp_price = 90.0   # TP = entry - 10 (short)

        self.position = Position(
            state=PositionState.LONG_ACTIVE if side_lower == "long" else PositionState.SHORT_ACTIVE,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            position_size=1.0,
            entry_time=int(datetime.now(tz=timezone.utc).timestamp() * 1000),
            side=side_lower,
        )

        print(f"[LiveS2B] TEST: forced {side_lower.upper()} entry={entry_price} sl={sl_price} tp={tp_price}")

    async def on_kline_close(self, kline_close: KlineClose) -> None:
        """
        Triggered when 4H candle closes

        Args:
            kline_close: KlineClose dataclass from WebSocket
        """
        # Convert KlineClose to candle dict format expected by strategy
        candle = {
            "open_time": kline_close.close_time_ms - 4 * 3600 * 1000,  # Approximate
            "open": kline_close.open,
            "high": kline_close.high,
            "low": kline_close.low,
            "close": kline_close.close,
            "volume": kline_close.volume,
            "close_time": kline_close.close_time_ms,
        }

        print(f"[LiveS2B] 4H kline_close received: close={candle['close']:.2f} ts={kline_close.close_time_ms}")

        # Add candle to history
        self.candles.append(candle)
        if len(self.candles) > 500:
            # Keep only last 500 candles for memory efficiency
            self.candles = self.candles[-500:]

        # Recalculate indicators
        self._recalculate_indicators()

        # Evaluate signal (may be None, "long", or "short")
        signal = self._evaluate_signal()

        if signal is not None:
            # Attempt trade execution
            await self.execute_trade(signal)

        # Check active position SL/TP
        if self.position.state != PositionState.FLAT:
            await self._check_position_exit(candle)

    def _recalculate_indicators(self) -> None:
        """Recalculate all indicators for current candle set"""
        if len(self.candles) < 30:
            return  # Not enough data

        try:
            self.indicators = self.strategy.prepare(self.candles)
        except Exception as e:
            print(f"[LiveS2B] Indicator calculation error: {e}")

    def _evaluate_signal(self) -> str | None:
        """
        Evaluate entry signal using approved strategy

        Returns:
            "long", "short", or None
        """
        if len(self.candles) < 50:
            return None  # Warmup period

        if self.position.state != PositionState.FLAT:
            return None  # Already in position

        try:
            index = len(self.candles) - 1
            signal = self.strategy.signal(index, self.candles, self.indicators)
            return signal
        except Exception as e:
            print(f"[LiveS2B] Signal evaluation error: {e}")
            return None

    async def execute_trade(self, signal: str) -> None:
        """
        Execute entry order for signal (or close existing position)

        Entry orders are subject to risk gating (kill_switch, downgrade_level).
        Exit/close orders are always allowed.

        Args:
            signal: "long", "short", or "close"
        """
        if not signal or signal == "flat":
            return

        # Handle position close (from exit monitor) - ALWAYS ALLOWED
        if signal == "close":
            if self.position.state != PositionState.FLAT:
                await self._close_position(self.position.entry_price, "MANUAL_CLOSE")
            return

        # ========== RISK GATING (entry only) ==========
        snap = self.risk.get_latest()

        # Gate 1: Kill Switch
        if snap.kill_switch:
            log_msg = f"BLOCKED: kill_switch=true | {signal.upper()}"
            print(f"[LiveS2B] {log_msg}")
            await self.alert.send(
                event_type="KILL_BLOCK",
                symbol=self.symbol,
                payload={"signal": signal, "kill_switch": True},
            )
            return

        # Gate 2: Downgrade Level (qty reduction)
        qty_multiplier = 1.0
        if snap.downgrade_level >= 2:
            qty_multiplier = 0.5
            log_msg = f"DOWNGRADE: level={snap.downgrade_level} | qty_multiplier=0.5"
            print(f"[LiveS2B] {log_msg}")
            await self.alert.send(
                event_type="DOWNGRADE_APPLIED",
                symbol=self.symbol,
                payload={"level": snap.downgrade_level, "multiplier": qty_multiplier},
            )

        # Get current price (use close of last candle)
        entry_price = float(self.candles[-1]["close"])

        # Apply slippage
        slippage = self.slippage_bps / 10_000.0
        if signal == "long":
            entry_eff = entry_price * (1.0 + slippage)
        else:
            entry_eff = entry_price * (1.0 - slippage)

        # Calculate position size with downgrade multiplier
        qty = (self.notional / entry_eff) * qty_multiplier

        # Get SL/TP from strategy
        try:
            index = len(self.candles) - 1
            sl_price, tp_price = self.strategy.risk_levels(
                index=index,
                side=signal,
                entry_price=entry_eff,
                candles=self.candles,
                indicators=self.indicators,
                default_sl_pct=0.0015,
                default_tp_pct=0.0030,
            )
        except Exception as e:
            print(f"[LiveS2B] Risk calculation error: {e}")
            await self.alert.send(
                event_type="ERROR",
                symbol=self.symbol,
                payload={"error": str(e)},
            )
            return

        print(f"[LiveS2B] Entry signal: {signal.upper()}")
        print(f"  Entry: {entry_eff:.2f} | SL: {sl_price:.2f} | TP: {tp_price:.2f} | Size: {qty:.8f}")

        # Send order via executor
        from .execution import OrderRequest
        order_req = OrderRequest(
            symbol=self.symbol,
            side=signal,
            qty=qty,
            entry_price=entry_eff,
            sl_price=sl_price,
            tp_price=tp_price,
        )

        result = await self.executor.place_order(order_req)
        if not result.ok:
            print(f"[LiveS2B] Order placement failed: {result.error}")
            await self.alert.send(
                event_type="ERROR",
                symbol=self.symbol,
                payload={"error": result.error, "signal": signal},
            )
            return

        print(f"[LiveS2B] Order accepted: order_id={result.order_id}")

        # Send ENTRY alert
        await self.alert.send(
            event_type="ENTRY",
            symbol=self.symbol,
            payload={
                "side": signal,
                "entry_price": entry_eff,
                "sl_price": sl_price,
                "tp_price": tp_price,
                "qty": qty,
                "order_id": result.order_id,
            },
        )

        # Update state machine
        new_state = PositionState.LONG_ACTIVE if signal == "long" else PositionState.SHORT_ACTIVE
        self.position = Position(
            state=new_state,
            entry_price=entry_eff,
            sl_price=sl_price,
            tp_price=tp_price,
            position_size=qty,
            entry_time=int(self.candles[-1]["close_time"]),
            side=signal,
        )
        self.trades_executed += 1

    async def _check_position_exit(self, candle: dict[str, Any]) -> None:
        """Check if current position hits SL or TP"""
        if self.position.state == PositionState.FLAT:
            return

        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])

        sl = self.position.sl_price
        tp = self.position.tp_price
        side = self.position.side

        exit_reason = None
        exit_price = None

        if side == "long":
            if low <= sl:
                exit_price = sl
                exit_reason = "SL"
            elif high >= tp:
                exit_price = tp
                exit_reason = "TP"
        else:  # short
            if high >= sl:
                exit_price = sl
                exit_reason = "SL"
            elif low <= tp:
                exit_price = tp
                exit_reason = "TP"

        if exit_reason:
            await self._close_position(exit_price, exit_reason)

    async def _close_position(self, exit_price: float, reason: str) -> None:
        """Close active position"""
        now = time.time()
        if now - self._last_exit_ts < 3:
            print("[LiveS2B] Exit cooldown active, skipping duplicate exit call")
            return
        self._last_exit_ts = now

        entry = self.position.entry_price
        qty = self.position.position_size
        side = self.position.side

        if entry is None or qty is None:
            print("[LiveS2B] ERROR: Position missing entry or qty")
            self.position = Position(state=PositionState.FLAT)
            return

        # Calculate PnL
        if side == "long":
            pnl = (exit_price - entry) * qty
        else:
            pnl = (entry - exit_price) * qty

        # Deduct fees
        fee_rate = self.fee_bps / 10_000.0
        fee = ((entry * qty) + (exit_price * qty)) * fee_rate
        net_pnl = pnl - fee

        print(f"[LiveS2B] Position closed: {reason}")
        print(f"  Entry: {entry:.2f} | Exit: {exit_price:.2f} | GrossPnL: {pnl:.4f} | Fee: {fee:.4f} | NetPnL: {net_pnl:.4f}")

        self.pnl_realized += net_pnl

        # Send EXIT alert
        await self.alert.send(
            event_type="EXIT",
            symbol=self.symbol,
            payload={
                "reason": reason,
                "side": side,
                "entry_price": entry,
                "exit_price": exit_price,
                "pnl": net_pnl,
            },
        )

        # TODO: Send CLOSE order to exchange
        # await adapter.close_position(symbol=self.symbol)

        # Reset state
        self.position = Position(state=PositionState.FLAT)

        # Persist updated state
        self.save_state()

    def save_state(self) -> None:
        """Persist engine state to disk"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert position to dict, but preserve state as its value
        pos_dict = asdict(self.position)
        pos_dict["state"] = self.position.state.value

        state = {
            "position": pos_dict,
            "trades_executed": self.trades_executed,
            "pnl_realized": self.pnl_realized,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

        with self.state_file.open("w") as f:
            json.dump(state, f, indent=2, default=str)

        print(f"[LiveS2B] State saved to {self.state_file}")

    def load_state(self) -> None:
        """Restore engine state from disk"""
        if not self.state_file.exists():
            print(f"[LiveS2B] No saved state found at {self.state_file}")
            return

        try:
            with self.state_file.open() as f:
                state = json.load(f)

            p = state.get("position", {})
            # Position state should be stored as its .value (e.g., "flat")
            pos_state_str = p.get("state", "flat")
            # Convert from value back to Enum
            self.position = Position(
                state=PositionState(pos_state_str),
                entry_price=p.get("entry_price"),
                sl_price=p.get("sl_price"),
                tp_price=p.get("tp_price"),
                position_size=p.get("position_size"),
                entry_time=p.get("entry_time"),
                side=p.get("side"),
            )

            self.trades_executed = state.get("trades_executed", 0)
            self.pnl_realized = state.get("pnl_realized", 0.0)

            print(f"[LiveS2B] State restored from {self.state_file}")
            print(f"  Position: {self.position.state.value} | Trades: {self.trades_executed} | PnL: {self.pnl_realized:.4f}")
        except Exception as e:
            print(f"[LiveS2B] Error loading state: {e}")


if __name__ == "__main__":
    import os

    key = os.getenv("BINANCE_KEY", "")
    secret = os.getenv("BINANCE_SECRET", "")

    engine = LiveS2BEngine(
        project_root=Path(__file__).resolve().parents[3],
        apikey=key,
        secret=secret,
        testnet=True,
    )

    asyncio.run(engine.run())
