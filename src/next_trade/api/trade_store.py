from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).parent.parent.parent.parent


def _events_file() -> Path:
    return _project_root() / "logs" / "runtime" / "trade_updates.jsonl"


def _to_epoch_ms(value) -> int:
    if isinstance(value, (int, float)):
        value_int = int(value)
        return value_int if value_int > 10_000_000_000 else value_int * 1000
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except Exception:
            return int(datetime.now(timezone.utc).timestamp() * 1000)
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _as_float(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _as_int(value) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def append_order_trade_update(payload: dict) -> dict | None:
    order = payload.get("o")
    if not isinstance(order, dict):
        return None

    ts_ms = _to_epoch_ms(payload.get("E") or order.get("T"))
    order_id = str(order.get("i") or order.get("c") or f"ord-{ts_ms}")
    symbol = str(order.get("s") or "")
    side = str(order.get("S") or "")
    order_type = str(order.get("o") or "")
    status = str(order.get("X") or order.get("x") or "UNKNOWN")

    order_price = _as_float(order.get("p") or order.get("ap") or order.get("L"))
    order_qty = _as_float(order.get("q") or order.get("z") or order.get("l"))
    cum_qty = _as_float(order.get("z"))

    fill_qty = _as_float(order.get("l"))
    fill_price = _as_float(order.get("L") or order.get("ap") or order.get("p"))
    fee = _as_float(order.get("n"))
    realized_pnl = _as_float(order.get("rp"))
    raw_trade_id = order.get("t")
    trade_id = (
        str(raw_trade_id)
        if raw_trade_id not in (None, "", "0", 0)
        else f"{order_id}-{ts_ms}"
    )

    trace_id = str(order.get("c") or order.get("i") or payload.get("E") or ts_ms)

    record = {
        "ts": ts_ms,
        "event_type": "ORDER_TRADE_UPDATE",
        "trace_id": trace_id,
        "order": {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "status": status,
            "price": order_price,
            "qty": order_qty,
            "cum_qty": cum_qty,
        },
        "fill": {
            "trade_id": trade_id,
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "price": fill_price,
            "qty": fill_qty,
            "fee": fee,
        },
        "ledger": {
            "realized_pnl": realized_pnl,
        },
    }

    try:
        path = _events_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        return record

    return record


def _load_records(max_lines: int = 5000) -> list[dict]:
    path = _events_file()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    rows: list[dict] = []
    for line in lines[-max_lines:]:
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
        except Exception:
            continue
    return rows


def list_orders(limit: int) -> list[dict]:
    records = _load_records()
    latest_by_order_id: dict[str, dict] = {}

    for record in records:
        order = record.get("order")
        if not isinstance(order, dict):
            continue
        order_id = str(order.get("order_id") or "")
        if not order_id:
            continue
        ts = _as_int(record.get("ts"))
        existing = latest_by_order_id.get(order_id)
        existing_ts = _as_int(existing.get("ts")) if isinstance(existing, dict) else -1
        if ts >= existing_ts:
            latest_by_order_id[order_id] = {
                "order_id": order_id,
                "symbol": str(order.get("symbol") or ""),
                "side": str(order.get("side") or ""),
                "type": str(order.get("type") or ""),
                "status": str(order.get("status") or "UNKNOWN"),
                "price": _as_float(order.get("price")),
                "qty": _as_float(order.get("qty")),
                "ts": ts,
            }

    items = sorted(
        latest_by_order_id.values(),
        key=lambda item: _as_int(item.get("ts")),
        reverse=True,
    )
    return items[:limit]


def list_fills(limit: int) -> list[dict]:
    records = _load_records()
    fill_items: list[dict] = []

    for record in reversed(records):
        fill = record.get("fill")
        order = record.get("order")
        if not isinstance(fill, dict) or not isinstance(order, dict):
            continue
        fill_qty = _as_float(fill.get("qty"))
        if fill_qty <= 0:
            continue
        ts = _as_int(record.get("ts"))
        trade_id = str(fill.get("trade_id") or f"{fill.get('order_id')}-{ts}")
        fill_items.append(
            {
                "trade_id": trade_id,
                "order_id": str(fill.get("order_id") or order.get("order_id") or ""),
                "symbol": str(fill.get("symbol") or order.get("symbol") or ""),
                "side": str(fill.get("side") or order.get("side") or ""),
                "price": _as_float(fill.get("price")),
                "qty": fill_qty,
                "fee": _as_float(fill.get("fee")),
                "ts": ts,
            }
        )

    return fill_items[:limit]


def get_pnl_snapshot(point_count: int = 60) -> dict:
    records = _load_records()
    if not records:
        now = datetime.now(timezone.utc)
        points = []
        for index in range(point_count):
            ts = now - timedelta(minutes=(point_count - 1 - index))
            points.append({"ts": int(ts.timestamp()), "equity": 0.0})
        return {
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "equity": 0.0,
            "peak_equity": 0.0,
            "worst_dd": 0.0,
            "equity_curve": points,
        }

    timeline: list[tuple[int, float]] = []
    realized = 0.0
    for record in sorted(records, key=lambda item: _as_int(item.get("ts"))):
        realized += _as_float((record.get("ledger") or {}).get("realized_pnl"))
        timeline.append((_as_int(record.get("ts")), realized))

    last_ts_ms = timeline[-1][0]
    end = datetime.fromtimestamp(last_ts_ms / 1000, tz=timezone.utc)
    start = end - timedelta(minutes=point_count - 1)

    equity_curve = []
    cursor = 0
    running = 0.0
    for idx in range(point_count):
        point_dt = start + timedelta(minutes=idx)
        point_ms = int(point_dt.timestamp() * 1000)
        while cursor < len(timeline) and timeline[cursor][0] <= point_ms:
            running = timeline[cursor][1]
            cursor += 1
        equity_curve.append({"ts": int(point_dt.timestamp()), "equity": running})

    peak_equity = max((point["equity"] for point in equity_curve), default=0.0)
    current_equity = equity_curve[-1]["equity"] if equity_curve else 0.0
    worst_dd = min(
        (point["equity"] - peak_equity for point in equity_curve), default=0.0
    )

    return {
        "realized_pnl": realized,
        "unrealized_pnl": 0.0,
        "equity": current_equity,
        "peak_equity": peak_equity,
        "worst_dd": worst_dd,
        "equity_curve": equity_curve,
    }
