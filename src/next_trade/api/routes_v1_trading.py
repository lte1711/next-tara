from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from next_trade.config.creds import get_binance_testnet_creds
from .trade_store import list_fills, list_orders

router = APIRouter(prefix="/api/v1/trading", tags=["trading-v1"])

CONTRACT_VERSION = "v1"


class CancelOrderRequest(BaseModel):
    order_id: str
    symbol: str | None = None


def _load_env_fallback() -> None:
    # Default OFF. Keep only as emergency compatibility path.
    raw = str(os.getenv("NEXTTRADE_ROUTE_DOTENV_FALLBACK", "0")).strip().lower()
    if raw not in {"1", "true", "yes"}:
        return

    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    env_path = root / ".env"
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            key = k.strip()
            if key and os.getenv(key) is None:
                os.environ[key] = v.strip()
    except Exception:
        pass


def _binance_creds() -> tuple[str, str, str]:
    _load_env_fallback()
    creds = get_binance_testnet_creds()
    key_value = creds.api_key
    sec_value = creds.api_secret
    base_url = os.getenv("BINANCE_TESTNET_BASE_URL", "https://demo-fapi.binance.com")
    return key_value, sec_value, base_url.rstrip("/")


def _signed_futures_request(method: str, path: str, params: dict) -> dict | list:
    import json
    from urllib.request import Request, urlopen

    key_value, sec_value, base_url = _binance_creds()
    if not key_value or not sec_value:
        raise HTTPException(status_code=503, detail="Missing Binance API credentials")

    payload = dict(params)
    # Use exchange server time first to avoid -1021 clock drift errors.
    timestamp = int(time.time() * 1000)
    try:
        time_req = Request(f"{base_url}/fapi/v1/time", method="GET")
        with urlopen(time_req, timeout=5) as time_resp:
            raw = time_resp.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            srv = data.get("serverTime")
            if srv is not None:
                timestamp = int(srv)
    except Exception:
        pass

    payload["timestamp"] = str(timestamp)
    payload["recvWindow"] = str(payload.get("recvWindow", "10000"))
    query_string = urlencode(payload)
    signature = hmac.new(
        sec_value.encode(),
        query_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    payload["signature"] = signature
    full_query = urlencode(payload)
    url = f"{base_url}{path}?{full_query}"

    req = Request(url, method=method.upper())
    req.add_header("X-MBX-APIKEY", key_value)
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=10) as response:
            data = response.read().decode("utf-8")
            return json.loads(data) if data else {}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Exchange request failed: {exc}")


def _symbol_from_order_id(order_id: str) -> str | None:
    for item in list_orders(200):
        if str(item.get("order_id") or "") == str(order_id):
            symbol = str(item.get("symbol") or "").strip().upper()
            if symbol:
                return symbol
    return None


@router.get("/orders")
def get_trading_orders(limit: int = Query(default=20, ge=1, le=200)):
    items = list_orders(limit)
    return {
        "items": items[:limit],
        "count": len(items[:limit]),
        "server_ts": datetime.now(timezone.utc).isoformat(),
        "contract_version": CONTRACT_VERSION,
    }


@router.get("/fills")
def get_trading_fills(limit: int = Query(default=20, ge=1, le=200)):
    items = list_fills(limit)
    return {
        "items": items[:limit],
        "count": len(items[:limit]),
        "server_ts": datetime.now(timezone.utc).isoformat(),
        "contract_version": CONTRACT_VERSION,
    }


@router.get("/open_orders")
@router.get("/open-orders")
def get_open_orders():
    orders = _signed_futures_request("GET", "/fapi/v1/openOrders", {})
    items = orders if isinstance(orders, list) else []
    return {
        "items": items,
        "count": len(items),
        "server_ts": datetime.now(timezone.utc).isoformat(),
        "contract_version": CONTRACT_VERSION,
    }


@router.get("/positions")
def get_trading_positions():
    account = _signed_futures_request("GET", "/fapi/v2/account", {})
    raw_positions = account.get("positions", []) if isinstance(account, dict) else []
    items = []
    for position in raw_positions:
        if not isinstance(position, dict):
            continue
        try:
            qty = float(position.get("positionAmt") or 0)
        except Exception:
            qty = 0.0
        if abs(qty) <= 0:
            continue
        items.append(position)
    return {
        "items": items,
        "count": len(items),
        "server_ts": datetime.now(timezone.utc).isoformat(),
        "contract_version": CONTRACT_VERSION,
    }


@router.post("/cancel")
def cancel_order(req: CancelOrderRequest):
    order_id = str(req.order_id).strip()
    if not order_id:
        raise HTTPException(status_code=400, detail="order_id is required")

    symbol = (req.symbol or "").strip().upper() or _symbol_from_order_id(order_id)
    if not symbol:
        raise HTTPException(
            status_code=400,
            detail="symbol is required (or resolvable from recent orders)",
        )

    result = _signed_futures_request(
        "DELETE",
        "/fapi/v1/order",
        {"symbol": symbol, "orderId": order_id},
    )
    return {"status": "ok", "result": result}
