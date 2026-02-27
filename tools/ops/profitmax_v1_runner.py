from __future__ import annotations

import argparse
import json
import math
import os
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import requests


@dataclass
class RunnerConfig:
    api_base: str = "http://127.0.0.1:8100"
    symbol: str = "BTCUSDT"
    session_hours: float = 2.0
    max_positions: int = 1
    base_qty: float = 0.002
    loop_sec: float = 5.0
    min_order_interval_sec: float = 30.0
    data_stall_sec: float = 10.0
    max_account_failures: int = 3
    session_loss_limit: float = -30.0
    cooldown_minutes: int = 10
    max_position_minutes: int = 10
    evidence_path: str = "logs/runtime/profitmax_v1_events.jsonl"
    summary_path: str = "logs/runtime/profitmax_v1_summary.json"
    dry_run: bool = False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class ProfitMaxV1Runner:
    def __init__(self, config: RunnerConfig):
        self.config = config
        self.project_root = Path(__file__).resolve().parents[2]
        self.session = requests.Session()
        self.prices: deque[float] = deque(maxlen=600)
        self.returns: deque[float] = deque(maxlen=600)

        self.last_price_ts: datetime | None = None
        self.last_order_ts: datetime | None = None
        self.last_heartbeat_ts: datetime | None = None

        self.kill = False
        self.account_failures = 0
        self.session_realized_pnl = 0.0

        self.position: dict[str, Any] | None = None
        self.strategy_stats: dict[str, dict[str, float]] = {
            "trend_momentum": {
                "ewma_pnl": 0.0,
                "trades": 0.0,
                "wins": 0.0,
                "losses": 0.0,
                "loss_streak": 0.0,
            },
            "mean_reversion": {
                "ewma_pnl": 0.0,
                "trades": 0.0,
                "wins": 0.0,
                "losses": 0.0,
                "loss_streak": 0.0,
            },
            "vol_breakout": {
                "ewma_pnl": 0.0,
                "trades": 0.0,
                "wins": 0.0,
                "losses": 0.0,
                "loss_streak": 0.0,
            },
        }
        self.cooldowns: dict[str, datetime] = {}

        raw_evidence_path = Path(self.config.evidence_path)
        raw_summary_path = Path(self.config.summary_path)
        self.evidence_path = (
            raw_evidence_path
            if raw_evidence_path.is_absolute()
            else self.project_root / raw_evidence_path
        )
        self.summary_path = (
            raw_summary_path
            if raw_summary_path.is_absolute()
            else self.project_root / raw_summary_path
        )
        self.lock_path = self.project_root / "logs/runtime/profitmax_v1_runner.lock"

    def _log_event(self, event_type: str, payload: dict[str, Any]) -> None:
        row = {
            "ts": utc_now().isoformat(),
            "event_type": event_type,
            "symbol": self.config.symbol,
            "payload": payload,
        }
        append_jsonl(self.evidence_path, row)

    def _http_get(self, path: str, timeout: float = 5.0) -> Any:
        response = self.session.get(f"{self.config.api_base}{path}", timeout=timeout)
        response.raise_for_status()
        return response.json()

    def _http_post(
        self, path: str, payload: dict[str, Any], timeout: float = 10.0
    ) -> Any:
        response = self.session.post(
            f"{self.config.api_base}{path}",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    def _fetch_mark_price(self) -> float:
        resp = self.session.get(
            f"https://demo-fapi.binance.com/fapi/v1/ticker/price?symbol={self.config.symbol}",
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        return float(data["price"])

    def _refresh_account_health(self) -> bool:
        try:
            _ = self._http_get("/api/investor/account", timeout=8)
            self.account_failures = 0
            return True
        except Exception as exc:
            self.account_failures += 1
            self._log_event(
                "ACCOUNT_FAIL",
                {
                    "count": self.account_failures,
                    "error": str(exc),
                },
            )
            if self.account_failures >= self.config.max_account_failures:
                self.kill = True
                self._log_event(
                    "KILL_SWITCH",
                    {
                        "reason": "account_check_failed",
                        "failures": self.account_failures,
                    },
                )
            return False

    def _update_market(self) -> bool:
        try:
            price = self._fetch_mark_price()
        except Exception as exc:
            self._log_event("PRICE_FETCH_FAIL", {"error": str(exc)})
            return False

        if self.prices:
            prev = self.prices[-1]
            if prev > 0:
                self.returns.append((price - prev) / prev)

        self.prices.append(price)
        self.last_price_ts = utc_now()
        return True

    def _classify_regime(self) -> str:
        if len(self.prices) < 30 or len(self.returns) < 20:
            return "warmup"

        ma_short = mean(list(self.prices)[-10:])
        ma_long = mean(list(self.prices)[-30:])
        trend_strength = abs((ma_short - ma_long) / ma_long) if ma_long else 0.0
        vol = pstdev(self.returns) if len(self.returns) >= 10 else 0.0

        if vol > 0.0015:
            return "high_vol"
        if trend_strength > 0.0008:
            return "trend"
        return "range"

    def _strategy_scores(self) -> dict[str, float]:
        if len(self.prices) < 40 or len(self.returns) < 20:
            return {
                "trend_momentum": 0.0,
                "mean_reversion": 0.0,
                "vol_breakout": 0.0,
            }

        p = list(self.prices)
        r = list(self.returns)
        price = p[-1]

        ma_fast = mean(p[-8:])
        ma_slow = mean(p[-24:])
        momentum_score = ((ma_fast - ma_slow) / ma_slow) * 1000 if ma_slow else 0.0

        window = p[-30:]
        mu = mean(window)
        sigma = pstdev(window) if len(window) > 1 else 0.0
        z = (price - mu) / sigma if sigma > 0 else 0.0
        # Surgery-001: tighten mean_reversion z-score threshold 0.8σ → 2.5σ
        meanrev_score = -z if abs(z) >= 2.5 else 0.0

        recent_high = max(p[-20:])
        recent_low = min(p[-20:])
        breakout_score = 0.0
        if price > recent_high * 1.00015:
            breakout_score = 1.2
        elif price < recent_low * 0.99985:
            breakout_score = -1.2

        vol_adj = pstdev(r[-20:]) if len(r) >= 20 else 0.0
        breakout_score *= 1.0 + min(vol_adj * 200, 1.0)

        return {
            "trend_momentum": momentum_score,
            "mean_reversion": meanrev_score,
            "vol_breakout": breakout_score,
        }

    def _allocator_weights(self, regime: str) -> dict[str, float]:
        base = {}
        for sid, stats in self.strategy_stats.items():
            base[sid] = max(0.1, 1.0 + stats["ewma_pnl"])

        if regime == "trend":
            base["trend_momentum"] *= 1.4
        elif regime == "range":
            base["mean_reversion"] *= 1.4
        elif regime == "high_vol":
            base["vol_breakout"] *= 1.4

        total = sum(base.values())
        return (
            {k: v / total for k, v in base.items()}
            if total > 0
            else {k: 1 / 3 for k in base}
        )

    def _choose_signal(self, regime: str) -> tuple[str, float, float]:
        scores = self._strategy_scores()
        weights = self._allocator_weights(regime)

        best_sid = "trend_momentum"
        best_strength = 0.0
        best_raw = 0.0
        for sid, score in scores.items():
            strength = score * weights.get(sid, 0.0)
            if abs(strength) > abs(best_strength):
                best_sid = sid
                best_strength = strength
                best_raw = score

        return best_sid, best_raw, best_strength

    def _should_enter(self, signal_strength: float) -> bool:
        if self.position is not None:
            return False
        if abs(signal_strength) < 0.12:
            return False
        if (
            self.last_order_ts
            and (utc_now() - self.last_order_ts).total_seconds()
            < self.config.min_order_interval_sec
        ):
            return False
        return True

    def _current_vol(self) -> float:
        if len(self.returns) < 20:
            return 0.0008
        return max(0.0004, pstdev(list(self.returns)[-20:]))

    def _compute_qty(self, requested_qty: float) -> dict[str, Any]:
        """Adjust qty upward to meet Binance min notional ($100 USDT, step 0.001 BTC)."""
        MIN_NOTIONAL = 100.0
        STEP_SIZE = 0.001
        price = self.prices[-1] if self.prices else 0.0
        if price <= 0:
            return {
                "qty": requested_qty,
                "price": price,
                "qty_before": requested_qty,
                "qty_after": requested_qty,
                "adjusted": False,
            }
        steps_needed = math.ceil(MIN_NOTIONAL / price / STEP_SIZE)
        min_qty = round(steps_needed * STEP_SIZE, 3)
        qty_after = round(max(requested_qty, min_qty), 3)
        return {
            "qty": qty_after,
            "price": price,
            "min_notional": MIN_NOTIONAL,
            "qty_before": requested_qty,
            "qty_after": qty_after,
            "computed_notional": round(qty_after * price, 4),
            "adjusted": qty_after != requested_qty,
        }

    def _place_order(self, side: str, quantity: float) -> dict[str, Any]:
        if self.config.dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "side": side,
                "quantity": quantity,
                "trace_id": f"dry-{uuid.uuid4().hex[:10]}",
            }

        qty_info = self._compute_qty(quantity)
        if qty_info["adjusted"]:
            self._log_event("QTY_ADJUSTED", qty_info)
        quantity = qty_info["qty"]

        payload = {
            "symbol": self.config.symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
        }
        return self._http_post("/api/investor/order", payload, timeout=12)

    def _enter_position(
        self, strategy_id: str, regime: str, signal_score: float, expected_edge: float
    ) -> None:
        side = "BUY" if signal_score > 0 else "SELL"
        vol = self._current_vol()
        tp_pct = clamp(vol * 6, 0.0015, 0.0035)
        sl_pct = clamp(vol * 8, 0.0025, 0.0060)
        entry_price = self.prices[-1]

        # Surgery-001: min expected profit gate (ExpectedProfit >= 2.5 × EstimatedFee)
        qty = self.config.base_qty
        estimated_fee = entry_price * qty * 0.0004 * 2  # round-trip taker fee
        expected_profit = tp_pct * qty * entry_price
        fee_ratio = expected_profit / estimated_fee if estimated_fee > 0 else 0.0
        if fee_ratio < 2.5:
            self._log_event(
                "STRATEGY_BLOCKED",
                {
                    "strategy_id": strategy_id,
                    "regime": regime,
                    "reason": "Surgery-001: min_edge_gate (ExpectedProfit < 2.5x fee)",
                    "expected_profit": round(expected_profit, 6),
                    "estimated_fee": round(estimated_fee, 6),
                    "fee_ratio": round(fee_ratio, 3),
                },
            )
            return

        risk_budget = 1.0 / max(1, self.config.max_positions)
        trace_id = f"pmx-{uuid.uuid4().hex[:12]}"

        result = self._place_order(side=side, quantity=self.config.base_qty)
        self.last_order_ts = utc_now()

        self.position = {
            "side": side,
            "qty": self.config.base_qty,
            "entry_price": entry_price,
            "entry_ts": utc_now(),
            "strategy_id": strategy_id,
            "regime": regime,
            "signal_score": signal_score,
            "expected_edge": expected_edge,
            "risk_budget": risk_budget,
            "trace_id": trace_id,
            "tp_pct": tp_pct,
            "sl_pct": sl_pct,
            "entry_order": result,
        }

        self._log_event(
            "ENTRY",
            {
                "strategy_id": strategy_id,
                "regime": regime,
                "signal_score": signal_score,
                "expected_edge": expected_edge,
                "risk_budget": risk_budget,
                "trace_id": trace_id,
                "side": side,
                "qty": self.config.base_qty,
                "entry_price": entry_price,
                "tp_pct": tp_pct,
                "sl_pct": sl_pct,
            },
        )

    def _should_exit(self, price: float) -> tuple[bool, str]:
        if self.position is None:
            return False, ""

        entry_price = float(self.position["entry_price"])
        side = self.position["side"]
        tp_pct = float(self.position["tp_pct"])
        sl_pct = float(self.position["sl_pct"])
        held_seconds = (utc_now() - self.position["entry_ts"]).total_seconds()

        if side == "BUY":
            if price >= entry_price * (1 + tp_pct):
                return True, "tp"
            if price <= entry_price * (1 - sl_pct):
                return True, "sl"
        else:
            if price <= entry_price * (1 - tp_pct):
                return True, "tp"
            if price >= entry_price * (1 + sl_pct):
                return True, "sl"

        if held_seconds >= self.config.max_position_minutes * 60:
            return True, "timeout"

        return False, ""

    def _close_position(self, reason: str) -> None:
        if self.position is None:
            return

        side = "SELL" if self.position["side"] == "BUY" else "BUY"
        result = self._place_order(side=side, quantity=float(self.position["qty"]))
        exit_price = self.prices[-1]
        entry_price = float(self.position["entry_price"])
        qty = float(self.position["qty"])

        gross = (exit_price - entry_price) * qty
        if self.position["side"] == "SELL":
            gross = -gross

        fee = (entry_price * qty + exit_price * qty) * 0.0004
        pnl = gross - fee
        self.session_realized_pnl += pnl

        sid = str(self.position["strategy_id"])
        stats = self.strategy_stats[sid]
        stats["trades"] += 1
        stats["ewma_pnl"] = stats["ewma_pnl"] * 0.9 + pnl * 0.1

        if pnl >= 0:
            stats["wins"] += 1
            stats["loss_streak"] = 0
        else:
            stats["losses"] += 1
            stats["loss_streak"] += 1
            if stats["loss_streak"] >= 5:
                self.cooldowns[sid] = utc_now() + timedelta(
                    minutes=self.config.cooldown_minutes
                )
                self._log_event(
                    "COOLDOWN",
                    {
                        "strategy_id": sid,
                        "loss_streak": stats["loss_streak"],
                        "cooldown_until": self.cooldowns[sid].isoformat(),
                    },
                )

        self._log_event(
            "EXIT",
            {
                "strategy_id": sid,
                "trace_id": self.position["trace_id"],
                "reason": reason,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "qty": qty,
                "pnl": pnl,
                "session_realized_pnl": self.session_realized_pnl,
                "exit_order": result,
            },
        )

        self.position = None
        self.last_order_ts = utc_now()

        if self.session_realized_pnl <= self.config.session_loss_limit:
            self.kill = True
            self._log_event(
                "KILL_SWITCH",
                {
                    "reason": "session_loss_limit",
                    "session_realized_pnl": self.session_realized_pnl,
                    "limit": self.config.session_loss_limit,
                },
            )

    def _write_summary(self) -> None:
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            "ts": utc_now().isoformat(),
            "symbol": self.config.symbol,
            "session_realized_pnl": self.session_realized_pnl,
            "kill": self.kill,
            "position_open": self.position is not None,
            "strategy_stats": self.strategy_stats,
            "cooldowns": {k: v.isoformat() for k, v in self.cooldowns.items()},
        }
        self.summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _acquire_lock(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        if self.lock_path.exists():
            try:
                stale = json.loads(self.lock_path.read_text(encoding="utf-8"))
                stale_pid = int(stale.get("pid", 0))
            except Exception:
                stale_pid = 0

            if stale_pid and self._pid_alive(stale_pid):
                self._log_event(
                    "RUN_SKIPPED",
                    {
                        "reason": "lock_exists",
                        "existing_pid": stale_pid,
                    },
                )
                return False

            try:
                self.lock_path.unlink()
            except OSError:
                pass

        try:
            fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            self._log_event("RUN_SKIPPED", {"reason": "lock_race"})
            return False

        with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
            lock_file.write(
                json.dumps({"pid": os.getpid(), "ts": utc_now().isoformat()})
            )
        return True

    def _release_lock(self) -> None:
        try:
            if self.lock_path.exists():
                self.lock_path.unlink()
        except OSError:
            pass

    def run(self) -> int:
        if not self._acquire_lock():
            return 2

        started_at = utc_now()
        end_at = started_at + timedelta(hours=self.config.session_hours)

        try:
            self._log_event(
                "RUN_START",
                {
                    "session_hours": self.config.session_hours,
                    "symbol": self.config.symbol,
                    "max_positions": self.config.max_positions,
                    "base_qty": self.config.base_qty,
                    "dry_run": self.config.dry_run,
                },
            )

            while utc_now() < end_at and not self.kill:
                cycle_ok = self._update_market()
                if not cycle_ok:
                    time.sleep(self.config.loop_sec)
                    continue

                if not self._refresh_account_health():
                    time.sleep(self.config.loop_sec)
                    continue

                if (
                    self.last_price_ts
                    and (utc_now() - self.last_price_ts).total_seconds()
                    > self.config.data_stall_sec
                ):
                    self._log_event(
                        "DATA_STALL",
                        {"seconds": (utc_now() - self.last_price_ts).total_seconds()},
                    )
                    time.sleep(self.config.loop_sec)
                    continue

                regime = self._classify_regime()
                strategy_id, raw_score, weighted_score = self._choose_signal(regime)
                now = utc_now()

                cooldown_until = self.cooldowns.get(strategy_id)
                in_cooldown = cooldown_until is not None and now < cooldown_until

                # Surgery-001: block mean_reversion and trend_momentum in range regime
                _RANGE_BLOCKED = {"mean_reversion", "trend_momentum"}
                range_blocked = regime == "range" and strategy_id in _RANGE_BLOCKED
                if range_blocked:
                    self._log_event(
                        "STRATEGY_BLOCKED",
                        {
                            "strategy_id": strategy_id,
                            "regime": regime,
                            "reason": "Surgery-001: range regime entry blocked",
                            "weighted_score": round(weighted_score, 6),
                        },
                    )

                if (
                    self.position is None
                    and not in_cooldown
                    and regime != "warmup"
                    and not range_blocked
                    and self._should_enter(weighted_score)
                ):
                    try:
                        self._enter_position(
                            strategy_id=strategy_id,
                            regime=regime,
                            signal_score=raw_score,
                            expected_edge=abs(weighted_score),
                        )
                    except Exception as exc:
                        self.last_order_ts = utc_now()
                        self._log_event(
                            "ENTRY_FAIL",
                            {
                                "strategy_id": strategy_id,
                                "regime": regime,
                                "error": str(exc),
                            },
                        )

                if self.position is not None:
                    exit_now, reason = self._should_exit(self.prices[-1])
                    if exit_now:
                        try:
                            self._close_position(reason=reason)
                        except Exception as exc:
                            self.last_order_ts = utc_now()
                            self._log_event(
                                "EXIT_FAIL",
                                {
                                    "reason": reason,
                                    "error": str(exc),
                                },
                            )

                if (
                    self.last_heartbeat_ts is None
                    or (now - self.last_heartbeat_ts).total_seconds() >= 60
                ):
                    self.last_heartbeat_ts = now
                    self._log_event(
                        "HEARTBEAT",
                        {
                            "regime": regime,
                            "price": self.prices[-1],
                            "position_open": self.position is not None,
                            "session_realized_pnl": self.session_realized_pnl,
                        },
                    )
                    self._write_summary()

                time.sleep(self.config.loop_sec)

            if self.position is not None and not self.kill:
                try:
                    self._close_position(reason="session_end")
                except Exception as exc:
                    self._log_event(
                        "EXIT_FAIL",
                        {
                            "reason": "session_end",
                            "error": str(exc),
                        },
                    )

            self._write_summary()
            self._log_event(
                "RUN_END",
                {
                    "kill": self.kill,
                    "session_realized_pnl": self.session_realized_pnl,
                },
            )
            return 0
        finally:
            self._release_lock()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PROFITMAX v1 testnet runner")
    parser.add_argument("--session-hours", type=float, default=2.0)
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--max-positions", type=int, default=1)
    parser.add_argument("--base-qty", type=float, default=0.002)
    parser.add_argument("--loop-sec", type=float, default=5.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-position-minutes", type=int, default=10)
    parser.add_argument(
        "--evidence-path", type=str, default="logs/runtime/profitmax_v1_events.jsonl"
    )
    parser.add_argument(
        "--summary-path", type=str, default="logs/runtime/profitmax_v1_summary.json"
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    cfg = RunnerConfig(
        symbol=args.symbol.upper(),
        session_hours=args.session_hours,
        max_positions=max(1, args.max_positions),
        base_qty=max(0.001, args.base_qty),
        loop_sec=max(1.0, args.loop_sec),
        dry_run=bool(args.dry_run),
        evidence_path=args.evidence_path,
        summary_path=args.summary_path,
        max_position_minutes=max(1, args.max_position_minutes),
    )
    runner = ProfitMaxV1Runner(cfg)
    return runner.run()


if __name__ == "__main__":
    raise SystemExit(main())
