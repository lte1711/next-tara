from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class StrategyParams:
    sl_pct: float = 0.0015
    tp_pct: float = 0.0030


class BaseStrategy(ABC):
    name: str = "base"

    @abstractmethod
    def prepare(self, candles: list[dict[str, Any]]) -> dict[str, list[float | None]]:
        raise NotImplementedError()

    @abstractmethod
    def signal(
        self,
        index: int,
        candles: list[dict[str, Any]],
        indicators: dict[str, list[float | None]],
    ) -> str | None:
        raise NotImplementedError()

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
        if side == "long":
            sl = entry_price * (1.0 - default_sl_pct)
            tp = entry_price * (1.0 + default_tp_pct)
        else:
            sl = entry_price * (1.0 + default_sl_pct)
            tp = entry_price * (1.0 - default_tp_pct)
        return sl, tp
