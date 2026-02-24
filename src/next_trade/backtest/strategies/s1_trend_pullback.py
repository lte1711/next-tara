from __future__ import annotations

from typing import Any

from ..indicators import atr, ema, rsi
from ..strategy_base import BaseStrategy


class S1TrendPullbackStrategy(BaseStrategy):
    name = "s1_trend_pullback"

    def prepare(self, candles: list[dict[str, Any]]) -> dict[str, list[float | None]]:
        close = [float(c["close"]) for c in candles]
        high = [float(c["high"]) for c in candles]
        low = [float(c["low"]) for c in candles]
        return {
            "ema50": ema(close, 50),
            "ema200": ema(close, 200),
            "rsi14": rsi(close, 14),
            "atr14": atr(high, low, close, 14),
        }

    def signal(
        self,
        index: int,
        candles: list[dict[str, Any]],
        indicators: dict[str, list[float | None]],
    ) -> str | None:
        if index < 201:
            return None

        ema50 = indicators["ema50"][index]
        ema200 = indicators["ema200"][index]
        rsi_now = indicators["rsi14"][index]
        rsi_prev = indicators["rsi14"][index - 1]
        close_now = float(candles[index]["close"])
        close_prev = float(candles[index - 1]["close"])

        if ema50 is None or ema200 is None or rsi_now is None or rsi_prev is None:
            return None

        long_trend = ema50 > ema200
        short_trend = ema50 < ema200

        long_pullback_resume = (40.0 <= rsi_prev <= 60.0) and (rsi_now > rsi_prev) and (close_now > close_prev)
        short_pullback_resume = (40.0 <= rsi_prev <= 60.0) and (rsi_now < rsi_prev) and (close_now < close_prev)

        if long_trend and long_pullback_resume:
            return "long"
        if short_trend and short_pullback_resume:
            return "short"
        return None
