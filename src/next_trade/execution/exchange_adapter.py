from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict


class ExchangeReject(Exception):
    def __init__(self, exchange: str, reason_code: "ExchangeRejectReason", message: str = ""):
        super().__init__(message)
        self.exchange = exchange
        self.reason_code = reason_code
        self.message = message


class ExchangeRejectReason(Enum):
    EXCHANGE_ERROR = "EXCHANGE_ERROR"
    MIN_NOTIONAL = "MIN_NOTIONAL"
    INVALID_ORDER_TYPE = "INVALID_ORDER_TYPE"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    RATE_LIMIT = "RATE_LIMIT"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"


@dataclass
class PlaceOrderRequest:
    trace_id: str
    symbol: str
    side: str
    qty: float
    price: float
    order_type: str = "LIMIT"


@dataclass
class PlaceOrderResult:
    exchange: str
    exchange_order_id: str
    symbol: str
    side: str
    qty: float
    price: float
    status: str
    timestamp: int


@dataclass
class ExchangeHealth:
    ok: bool
    details: Optional[Dict] = None


class BaseExchangeAdapter:
    async def get_exchange_name(self) -> str:  # pragma: no cover - abstract
        raise NotImplementedError()

    async def place_order(self, req: PlaceOrderRequest) -> PlaceOrderResult:  # pragma: no cover
        raise NotImplementedError()

    async def cancel_all(self) -> None:  # pragma: no cover
        raise NotImplementedError()

    async def get_health(self) -> ExchangeHealth:  # pragma: no cover
        raise NotImplementedError()
