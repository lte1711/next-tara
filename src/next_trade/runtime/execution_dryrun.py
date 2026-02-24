"""
Dry-Run Execution Adapter

For testing and validation without real trades.
Generates fake order IDs and logs all execution decisions.
"""
from __future__ import annotations

import time

from .execution import ExecutionAdapter, OrderRequest, OrderResult


class DryRunExecutionAdapter(ExecutionAdapter):
    """Simulated order execution for dry-run mode"""

    def __init__(self):
        self.order_count = 0

    async def place_order(self, req: OrderRequest) -> OrderResult:
        """
        Simulate order placement

        Always returns success with a fake order ID.
        """
        self.order_count += 1
        fake_id = f"DRY_{int(time.time()*1000)}_{self.order_count}"

        print(f"[DryRun.Execution] Order placed (simulated): {fake_id}")
        print(f"  Symbol: {req.symbol} | Side: {req.side} | Qty: {req.qty:.8f} | Type: {req.order_type}")

        return OrderResult(ok=True, order_id=fake_id)
