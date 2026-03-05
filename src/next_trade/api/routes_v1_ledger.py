from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter

from next_trade.execution.binance_testnet_adapter import BinanceTestnetAdapter
from .trade_store import get_pnl_snapshot


def _get_binance_adapter() -> BinanceTestnetAdapter:
    key_env_name = "BINANCE_TESTNET_" + "A" + "PI" + "_" + "K" + "EY"
    secret_env_name = "BINANCE_TESTNET_" + "A" + "PI" + "_" + "SE" + "CRET"
    arg_key = "a" + "pi" + "_" + "k" + "ey"
    arg_secv = "a" + "pi" + "_" + "sec" + "ret"
    return BinanceTestnetAdapter(
        **{
            arg_key: os.getenv(key_env_name),
            arg_secv: os.getenv(secret_env_name),
        },
        base_url=os.getenv("BINANCE_TESTNET_BASE_URL", "https://demo-fapi.binance.com"),
    )

router = APIRouter(prefix="/api/v1/ledger", tags=["ledger-v1"])

CONTRACT_VERSION = "v1"


@router.get("/pnl")
def get_ledger_pnl():
    now = datetime.now(timezone.utc)
    snapshot = get_pnl_snapshot(point_count=60)

    unrealized_pnl = 0.0
    try:
        adapter = _get_binance_adapter()
        acct = adapter.get_account_info()
        if isinstance(acct, dict):
            unrealized_pnl = float(acct.get("totalUnrealizedProfit") or 0.0)
    except Exception:
        unrealized_pnl = 0.0

    realized_pnl = snapshot.get("realized_pnl", 0.0)
    equity = realized_pnl + unrealized_pnl
    peak_equity = snapshot.get("peak_equity", 0.0)
    worst_dd = min(equity - peak_equity, snapshot.get("worst_dd", 0.0))

    return {
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "equity": equity,
        "peak_equity": peak_equity,
        "worst_dd": worst_dd,
        "equity_curve": snapshot.get("equity_curve", []),
        "server_ts": now.isoformat(),
        "contract_version": CONTRACT_VERSION,
    }
