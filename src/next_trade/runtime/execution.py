"""
Order Execution Adapter Interface

Defines contract for placing and managing orders.
Implementations can be dry-run, testnet, or production.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OrderRequest:
    """Request to place an order"""
    symbol: str
    side: str  # "long" or "short" for strategy, maps to "BUY" or "SELL"
    qty: float
    order_type: str = "MARKET"
    reduce_only: bool = False
    # For limit/OCO orders:
    entry_price: float | None = None
    sl_price: float | None = None
    tp_price: float | None = None


@dataclass
class OrderResult:
    """Result of order placement attempt"""
    ok: bool
    order_id: str | None = None
    error: str | None = None


class ExecutionAdapter:
    """Base adapter for order execution"""

    async def place_order(self, req: OrderRequest) -> OrderResult:
        """Place an order"""
        raise NotImplementedError
