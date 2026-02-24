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
    ) -> None:
        self.k = k
        self.m = m
        self.n = n
        self.sma_period = sma_period
        self.atr_period = atr_period

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
            return None

        if close_now > float(upper):
            return "long"
        if close_now < float(lower):
            return "short"
        return None

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
