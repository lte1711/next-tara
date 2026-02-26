from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/v1/trading", tags=["trading-v1"])

CONTRACT_VERSION = "v1"


@router.get("/orders")
def get_trading_orders(limit: int = Query(default=20, ge=1, le=200)):
    items = []
    return {
        "items": items[:limit],
        "count": len(items[:limit]),
        "server_ts": datetime.now(timezone.utc).isoformat(),
        "contract_version": CONTRACT_VERSION,
    }


@router.get("/fills")
def get_trading_fills(limit: int = Query(default=20, ge=1, le=200)):
    items = []
    return {
        "items": items[:limit],
        "count": len(items[:limit]),
        "server_ts": datetime.now(timezone.utc).isoformat(),
        "contract_version": CONTRACT_VERSION,
    }
