#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compute realized PnL from fills JSON exported by NEXT-TRADE API.

Assumptions:
- Each fill item has: price, qty, fee, side, ts (ms)
- Realized PnL is approximated using FIFO matching per symbol:
    - BUY increases position inventory
    - SELL reduces inventory; realized pnl = (sell_price - avg_buy_cost) * qty (FIFO lots)
- Fees are always subtracted from PnL (fee is positive number)
- Supports multiple symbols independently.

Outputs:
- Daily window (KST 00:00:00 ~ now)
- Total window (first fill ts ~ now)
- Per-symbol summary included.

This is "realized by matching" (trade accounting), not mark-to-market.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List


KST = timezone(timedelta(hours=9))


@dataclass
class Lot:
    qty: float
    price: float


def _to_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _get_kst_midnight(dt_kst: datetime) -> datetime:
    return datetime(dt_kst.year, dt_kst.month, dt_kst.day, 0, 0, 0, tzinfo=KST)


def _parse_items(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, dict) and "items" in obj and isinstance(obj["items"], list):
        return obj["items"]
    if isinstance(obj, list):
        return obj
    raise ValueError("Unsupported fills json format. Expect {items:[...]} or [...]")


def _symbol_of(item: Dict[str, Any]) -> str:
    for k in ("symbol", "s"):
        if k in item and item[k]:
            return str(item[k])
    return "UNKNOWN"


def _side_of(item: Dict[str, Any]) -> str:
    for k in ("side", "S"):
        if k in item and item[k]:
            return str(item[k]).upper()
    return "UNKNOWN"


def _ts_ms(item: Dict[str, Any]) -> int:
    for k in ("ts", "time", "timestamp", "T"):
        if k in item and item[k] is not None:
            try:
                return int(item[k])
            except Exception:
                pass
    return 0


def _qty(item: Dict[str, Any]) -> float:
    for k in ("qty", "q", "executedQty"):
        if k in item and item[k] is not None:
            return _to_float(item[k], 0.0)
    return 0.0


def _price(item: Dict[str, Any]) -> float:
    for k in ("price", "p"):
        if k in item and item[k] is not None:
            return _to_float(item[k], 0.0)
    return 0.0


def _fee(item: Dict[str, Any]) -> float:
    for k in ("fee", "commission"):
        if k in item and item[k] is not None:
            return abs(_to_float(item[k], 0.0))
    return 0.0


def fifo_realized_pnl(fills: List[Dict[str, Any]]) -> Dict[str, Any]:
    inv: Dict[str, List[Lot]] = {}
    per_symbol: Dict[str, Dict[str, float | int]] = {}

    realized_total = 0.0
    fees_total = 0.0
    trades_total = 0
    notional_total = 0.0

    fills_sorted = sorted(fills, key=_ts_ms)

    for it in fills_sorted:
        sym = _symbol_of(it)
        side = _side_of(it)
        qty = _qty(it)
        price = _price(it)
        fee = _fee(it)

        if qty <= 0 or price <= 0:
            continue
        notional = qty * price
        notional_total += notional

        inv.setdefault(sym, [])
        per_symbol.setdefault(
            sym,
            {
                "realized_pnl": 0.0,
                "fees": 0.0,
                "trades": 0,
                "buy_qty": 0.0,
                "sell_qty": 0.0,
                "open_qty_est": 0.0,
                "notional_sum": 0.0,
            },
        )
        per_symbol[sym]["notional_sum"] += notional

        fees_total += fee
        per_symbol[sym]["fees"] += fee

        if side == "BUY":
            inv[sym].append(Lot(qty=qty, price=price))
            per_symbol[sym]["buy_qty"] += qty
            trades_total += 1
            per_symbol[sym]["trades"] += 1

        elif side == "SELL":
            remaining = qty
            sell_qty_done = 0.0
            realized = 0.0

            while remaining > 1e-12 and inv[sym]:
                lot = inv[sym][0]
                take = min(remaining, lot.qty)
                realized += (price - lot.price) * take
                lot.qty -= take
                remaining -= take
                sell_qty_done += take
                if lot.qty <= 1e-12:
                    inv[sym].pop(0)

            realized_total += realized
            per_symbol[sym]["realized_pnl"] += realized
            per_symbol[sym]["sell_qty"] += sell_qty_done
            trades_total += 1
            per_symbol[sym]["trades"] += 1

        else:
            continue

    for sym, lots in inv.items():
        per_symbol[sym]["open_qty_est"] = sum(l.qty for l in lots)

    avg_fee_per_trade = (fees_total / trades_total) if trades_total else 0.0
    avg_gross_per_trade = (realized_total / trades_total) if trades_total else 0.0
    avg_notional_per_trade = (notional_total / trades_total) if trades_total else 0.0
    fee_rate_est = (fees_total / notional_total) if notional_total else 0.0
    fees_vs_gross_ratio = (fees_total / abs(realized_total)) if realized_total else 0.0

    return {
        "realized_pnl": realized_total - fees_total,
        "gross_realized_pnl": realized_total,
        "fees": fees_total,
        "trades": trades_total,
        "notional_sum": notional_total,
        "avg_fee_per_trade": avg_fee_per_trade,
        "avg_gross_per_trade": avg_gross_per_trade,
        "avg_notional_per_trade": avg_notional_per_trade,
        "fee_rate_est": fee_rate_est,
        "fees_vs_gross_ratio": fees_vs_gross_ratio,
        "per_symbol": per_symbol,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: pnl_daily_from_fills.py <fills_raw.json> [--out <report.json>] [--run-start-ms <epoch_ms>]")
        return 2

    in_path = Path(sys.argv[1]).expanduser()
    out_path = None
    run_start_ms = None
    if "--out" in sys.argv:
        idx = sys.argv.index("--out")
        if idx + 1 < len(sys.argv):
            out_path = Path(sys.argv[idx + 1]).expanduser()
    if "--run-start-ms" in sys.argv:
        idx = sys.argv.index("--run-start-ms")
        if idx + 1 < len(sys.argv):
            try:
                run_start_ms = int(sys.argv[idx + 1])
            except Exception:
                run_start_ms = None

    raw = json.loads(in_path.read_text(encoding="utf-8-sig"))
    items = _parse_items(raw)

    now_kst = datetime.now(KST)
    kst_midnight = _get_kst_midnight(now_kst)
    kst_midnight_ms = int(kst_midnight.timestamp() * 1000)

    fills_all = [it for it in items if _ts_ms(it) > 0]
    fills_daily = [it for it in fills_all if _ts_ms(it) >= kst_midnight_ms]
    fills_run = (
        [it for it in fills_all if _ts_ms(it) >= int(run_start_ms)]
        if run_start_ms is not None
        else fills_all
    )

    total_stats = fifo_realized_pnl(fills_all)
    daily_stats = fifo_realized_pnl(fills_daily)
    run_stats = fifo_realized_pnl(fills_run)

    first_ts_ms = min((_ts_ms(it) for it in fills_all), default=0)
    first_dt_kst = datetime.fromtimestamp(first_ts_ms / 1000, tz=KST) if first_ts_ms else None
    run_start_dt_kst = (
        datetime.fromtimestamp(int(run_start_ms) / 1000, tz=KST)
        if run_start_ms is not None
        else first_dt_kst
    )

    report = {
        "generated_at_kst": now_kst.isoformat(),
        "daily_window_kst": {
            "from": kst_midnight.isoformat(),
            "to": now_kst.isoformat(),
        },
        "total_window_kst": {
            "from": first_dt_kst.isoformat() if first_dt_kst else None,
            "to": now_kst.isoformat(),
        },
        "run_window_kst": {
            "from": run_start_dt_kst.isoformat() if run_start_dt_kst else None,
            "to": now_kst.isoformat(),
        },
        "daily": daily_stats,
        "run": run_stats,
        "total": total_stats,
        "notes": {
            "method": "FIFO realized pnl by matching BUY/SELL fills per symbol; fees subtracted; unmatched sell treated as 0 realized (conservative).",
        },
    }

    print(f"DAILY_WINDOW_KST = [{report['daily_window_kst']['from']} ~ {report['daily_window_kst']['to']}]")
    print(f"DAILY_REALIZED_PNL = {daily_stats['realized_pnl']:.8f} (gross={daily_stats['gross_realized_pnl']:.8f}, fees={daily_stats['fees']:.8f})")
    print(f"DAILY_TRADES = {daily_stats['trades']}")
    print(f"RUN_WINDOW_KST = [{report['run_window_kst']['from']} ~ {report['run_window_kst']['to']}]")
    print(f"RUN_REALIZED_PNL = {run_stats['realized_pnl']:.8f} (gross={run_stats['gross_realized_pnl']:.8f}, fees={run_stats['fees']:.8f})")
    print(f"RUN_TRADES = {run_stats['trades']}")
    print(f"TOTAL_WINDOW_KST = [{report['total_window_kst']['from']} ~ {report['total_window_kst']['to']}]")
    print(f"TOTAL_REALIZED_PNL = {total_stats['realized_pnl']:.8f} (gross={total_stats['gross_realized_pnl']:.8f}, fees={total_stats['fees']:.8f})")
    print(f"TOTAL_TRADES = {total_stats['trades']}")
    print(f"TOTAL_FEE_RATE_EST = {total_stats['fee_rate_est']:.8f}")
    print(f"SYMBOLS = {len(total_stats['per_symbol'])}")
    print("OK")

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
