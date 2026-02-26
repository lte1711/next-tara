from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/ledger", tags=["ledger-v1"])

CONTRACT_VERSION = "v1"


@router.get("/pnl")
def get_ledger_pnl():
    now = datetime.now(timezone.utc)
    points = []
    base_equity = 0.0
    for index in range(60):
        ts = now - timedelta(minutes=(59 - index))
        points.append({"ts": int(ts.timestamp()), "equity": base_equity})

    return {
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "equity": 0.0,
        "peak_equity": 0.0,
        "worst_dd": 0.0,
        "equity_curve": points,
        "server_ts": now.isoformat(),
        "contract_version": CONTRACT_VERSION,
    }
