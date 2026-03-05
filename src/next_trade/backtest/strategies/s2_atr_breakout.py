from __future__ import annotations

from typing import Any

from ..indicators import atr
from ..strategy_base import BaseStrategy


class S2AtrBreakoutStrategy(BaseStrategy):
    name = "s2_atr_breakout"

    def __init__(
        self,
        k: float = 2.0,
        m: float = 1.5,
        n: float = 3.0,
        sma_period: int = 20,
        atr_period: int = 14,
        ha_filter_enabled: bool = False,
        ha_confirm_n: int = 2,
        ha_lookback: int = 60,
    ) -> None:
        self.k = k
        self.m = m
        self.n = n
        self.sma_period = sma_period
        self.atr_period = atr_period
        self.ha_filter_enabled = bool(ha_filter_enabled)
        self.ha_confirm_n = max(1, int(ha_confirm_n))
        self.ha_lookback = max(5, int(ha_lookback))
        self.ha_last_debug: dict[str, Any] = {
            "enabled": self.ha_filter_enabled,
            "side": None,
            "ha_ok": None,
            "confirm_n": self.ha_confirm_n,
            "ha_last_open": None,
            "ha_last_close": None,
        }

    def prepare(self, candles: list[dict[str, Any]]) -> dict[str, list[float | None]]:
        close = [float(c["close"]) for c in candles]
        high = [float(c["high"]) for c in candles]
        low = [float(c["low"]) for c in candles]
        atr14 = atr(high, low, close, self.atr_period)
        sma20 = self._sma(close, self.sma_period)

        upper: list[float | None] = [None] * len(close)
        lower: list[float | None] = [None] * len(close)
        for i in range(len(close)):
            if sma20[i] is None or atr14[i] is None:
                continue
            upper[i] = float(sma20[i]) + (self.k * float(atr14[i]))
            lower[i] = float(sma20[i]) - (self.k * float(atr14[i]))

        return {
            "atr": atr14,
            "sma": sma20,
            "upper": upper,
            "lower": lower,
        }

    def signal(
        self,
        index: int,
        candles: list[dict[str, Any]],
        indicators: dict[str, list[float | None]],
    ) -> str | None:
        warmup = max(self.sma_period, self.atr_period)
        if index < warmup:
            return None

        close_now = float(candles[index]["close"])
        upper = indicators["upper"][index]
        lower = indicators["lower"][index]
        if upper is None or lower is None:
            self.ha_last_debug = {
                "enabled": self.ha_filter_enabled,
                "side": None,
                "ha_ok": None,
                "confirm_n": self.ha_confirm_n,
                "ha_last_open": None,
                "ha_last_close": None,
            }
            return None

        side: str | None = None
        if close_now > float(upper):
            side = "long"
        elif close_now < float(lower):
            side = "short"
        if side is None:
            self.ha_last_debug = {
                "enabled": self.ha_filter_enabled,
                "side": None,
                "ha_ok": None,
                "confirm_n": self.ha_confirm_n,
                "ha_last_open": None,
                "ha_last_close": None,
            }
            return None

        if not self.ha_filter_enabled:
            self.ha_last_debug = {
                "enabled": False,
                "side": side,
                "ha_ok": True,
                "confirm_n": self.ha_confirm_n,
                "ha_last_open": None,
                "ha_last_close": None,
            }
            return side

        ha_ok, debug = self._ha_filter_ok(side=side, index=index, candles=candles)
        self.ha_last_debug = debug
        if ha_ok:
            return side
        return None

    def _ha_filter_ok(
        self,
        *,
        side: str,
        index: int,
        candles: list[dict[str, Any]],
    ) -> tuple[bool, dict[str, Any]]:
        start = max(0, index - self.ha_lookback + 1)
        src = candles[start : index + 1]
        has = self._compute_heikin_ashi(src)
        if len(has) < self.ha_confirm_n:
            return False, {
                "enabled": True,
                "side": side,
                "ha_ok": False,
                "confirm_n": self.ha_confirm_n,
                "ha_last_open": None,
                "ha_last_close": None,
                "reason": "insufficient_ha_bars",
            }

        recent = has[-self.ha_confirm_n :]
        if side == "long":
            ok = all(c["ha_close"] > c["ha_open"] for c in recent)
        else:
            ok = all(c["ha_close"] < c["ha_open"] for c in recent)

        last = has[-1]
        return ok, {
            "enabled": True,
            "side": side,
            "ha_ok": ok,
            "confirm_n": self.ha_confirm_n,
            "ha_last_open": float(last["ha_open"]),
            "ha_last_close": float(last["ha_close"]),
        }

    @staticmethod
    def _compute_heikin_ashi(candles: list[dict[str, Any]]) -> list[dict[str, float]]:
        out: list[dict[str, float]] = []
        prev_ha_open: float | None = None
        prev_ha_close: float | None = None

        for c in candles:
            o = float(c["open"])
            h = float(c["high"])
            l = float(c["low"])
            cl = float(c["close"])

            ha_close = (o + h + l + cl) / 4.0
            if prev_ha_open is None or prev_ha_close is None:
                ha_open = (o + cl) / 2.0
            else:
                ha_open = (prev_ha_open + prev_ha_close) / 2.0
            ha_high = max(h, ha_open, ha_close)
            ha_low = min(l, ha_open, ha_close)

            out.append(
                {
                    "ha_open": ha_open,
                    "ha_close": ha_close,
                    "ha_high": ha_high,
                    "ha_low": ha_low,
                }
            )
            prev_ha_open = ha_open
            prev_ha_close = ha_close
        return out

    def risk_levels(
        self,
        index: int,
        side: str,
        entry_price: float,
        candles: list[dict[str, Any]],
        indicators: dict[str, list[float | None]],
        default_sl_pct: float,
        default_tp_pct: float,
    ) -> tuple[float, float]:
        atr_now = indicators["atr"][index]
        if atr_now is None or atr_now <= 0:
            return super().risk_levels(
                index=index,
                side=side,
                entry_price=entry_price,
                candles=candles,
                indicators=indicators,
                default_sl_pct=default_sl_pct,
                default_tp_pct=default_tp_pct,
            )

        atr_value = float(atr_now)
        if side == "long":
            sl = entry_price - (self.m * atr_value)
            tp = entry_price + (self.n * atr_value)
        else:
            sl = entry_price + (self.m * atr_value)
            tp = entry_price - (self.n * atr_value)
        return sl, tp

    @staticmethod
    def _sma(values: list[float], period: int) -> list[float | None]:
        out: list[float | None] = [None] * len(values)
        if period <= 0:
            return out

        running = 0.0
        for i, value in enumerate(values):
            running += value
            if i >= period:
                running -= values[i - period]
            if i >= period - 1:
                out[i] = running / period
        return out
