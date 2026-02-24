from __future__ import annotations


def ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if not values or period <= 1:
        return out

    alpha = 2.0 / (period + 1.0)
    if len(values) < period:
        return out

    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed

    for i in range(period, len(values)):
        current = (values[i] * alpha) + (prev * (1.0 - alpha))
        out[i] = current
        prev = current
    return out


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out

    gains = [0.0] * len(values)
    losses = [0.0] * len(values)
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains[i] = max(change, 0.0)
        losses[i] = max(-change, 0.0)

    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss)))

    for i in range(period + 1, len(values)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def atr(high: list[float], low: list[float], close: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(close)
    if len(close) <= period:
        return out

    tr: list[float] = [0.0] * len(close)
    for i in range(1, len(close)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    seed = sum(tr[1 : period + 1]) / period
    out[period] = seed
    prev = seed
    for i in range(period + 1, len(close)):
        current = ((prev * (period - 1)) + tr[i]) / period
        out[i] = current
        prev = current
    return out
