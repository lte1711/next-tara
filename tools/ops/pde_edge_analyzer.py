#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDE Edge Analyzer

Input:
- fills_raw_*.json exported by tools/ops/pnl_daily_run.ps1

What it computes:
- FIFO matched realized edge chunks (SELL closes against prior BUY lots)
- edge_after_fee per matched chunk:
    edge = (sell_price - buy_price) * qty - allocated_buy_fee - allocated_sell_fee
- distributions / histogram of edge_after_fee
- windowed summaries: DAILY / RUN / TOTAL
- suggested threshold candidates based on quantiles of positive edges

Notes:
- Conservative for unmatched SELL quantity: ignored (no synthetic short lot).
- This is execution-edge analytics, not mark-to-market.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


KST = timezone(timedelta(hours=9))


@dataclass
class Fill:
    ts: int
    symbol: str
    side: str
    price: float
    qty: float
    fee: float
    trade_id: str


@dataclass
class Lot:
    qty: float
    price: float
    fee_per_unit: float
    ts: int


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _parse_items(raw_obj: Any) -> list[dict]:
    if isinstance(raw_obj, dict) and isinstance(raw_obj.get("items"), list):
        return raw_obj["items"]
    if isinstance(raw_obj, list):
        return raw_obj
    raise ValueError("Unsupported fills json format")


def _as_fill(item: dict) -> Fill | None:
    ts = _to_int(item.get("ts") or item.get("time") or item.get("timestamp") or item.get("T"))
    symbol = str(item.get("symbol") or item.get("s") or "").upper()
    side = str(item.get("side") or item.get("S") or "").upper()
    price = _to_float(item.get("price") or item.get("p"))
    qty = _to_float(item.get("qty") or item.get("q") or item.get("executedQty"))
    fee = abs(_to_float(item.get("fee") or item.get("commission")))
    trade_id = str(item.get("trade_id") or item.get("id") or item.get("order_id") or f"{symbol}-{ts}")
    if ts <= 0 or not symbol or side not in {"BUY", "SELL"} or price <= 0 or qty <= 0:
        return None
    return Fill(ts=ts, symbol=symbol, side=side, price=price, qty=qty, fee=fee, trade_id=trade_id)


def _kst_midnight_ms(now_kst: datetime) -> int:
    dt = datetime(now_kst.year, now_kst.month, now_kst.day, tzinfo=KST)
    return int(dt.timestamp() * 1000)


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    if q <= 0:
        return sorted_vals[0]
    if q >= 1:
        return sorted_vals[-1]
    pos = (len(sorted_vals) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_vals[lo]
    w = pos - lo
    return sorted_vals[lo] * (1 - w) + sorted_vals[hi] * w


def _build_edges(fills: list[Fill]) -> list[dict[str, Any]]:
    inv: dict[str, list[Lot]] = {}
    edges: list[dict[str, Any]] = []

    for f in sorted(fills, key=lambda x: x.ts):
        inv.setdefault(f.symbol, [])
        if f.side == "BUY":
            fee_per_unit = (f.fee / f.qty) if f.qty > 0 else 0.0
            inv[f.symbol].append(Lot(qty=f.qty, price=f.price, fee_per_unit=fee_per_unit, ts=f.ts))
            continue

        remaining = f.qty
        sell_fee_per_unit = (f.fee / f.qty) if f.qty > 0 else 0.0
        while remaining > 1e-12 and inv[f.symbol]:
            lot = inv[f.symbol][0]
            take = min(remaining, lot.qty)
            gross = (f.price - lot.price) * take
            fee_alloc = (lot.fee_per_unit + sell_fee_per_unit) * take
            edge_after_fee = gross - fee_alloc
            edges.append(
                {
                    "symbol": f.symbol,
                    "close_ts": f.ts,
                    "open_ts": lot.ts,
                    "qty": take,
                    "open_price": lot.price,
                    "close_price": f.price,
                    "gross": gross,
                    "fee_alloc": fee_alloc,
                    "edge_after_fee": edge_after_fee,
                }
            )
            lot.qty -= take
            remaining -= take
            if lot.qty <= 1e-12:
                inv[f.symbol].pop(0)
    return edges


def _histogram(values: list[float], bins: int = 20) -> list[dict[str, float | int]]:
    if not values:
        return []
    vmin = min(values)
    vmax = max(values)
    if abs(vmax - vmin) <= 1e-12:
        return [{"bin_from": vmin, "bin_to": vmax, "count": len(values)}]
    width = (vmax - vmin) / bins
    counts = [0] * bins
    for v in values:
        idx = int((v - vmin) / width)
        if idx >= bins:
            idx = bins - 1
        if idx < 0:
            idx = 0
        counts[idx] += 1
    out: list[dict[str, float | int]] = []
    for i, c in enumerate(counts):
        lo = vmin + i * width
        hi = lo + width
        out.append({"bin_from": lo, "bin_to": hi, "count": c})
    return out


def _summarize_window(name: str, edges: list[dict[str, Any]]) -> dict[str, Any]:
    vals = [float(e["edge_after_fee"]) for e in edges]
    gross = sum(float(e["gross"]) for e in edges)
    fees = sum(float(e["fee_alloc"]) for e in edges)
    total = sum(vals)
    pos = [v for v in vals if v > 0]
    neg = [v for v in vals if v <= 0]
    svals = sorted(vals)
    spos = sorted(pos)
    summary = {
        "window": name,
        "matched_chunks": len(edges),
        "edge_after_fee_sum": total,
        "gross_sum": gross,
        "fee_alloc_sum": fees,
        "win_rate": (len(pos) / len(vals)) if vals else 0.0,
        "avg_edge_after_fee": (total / len(vals)) if vals else 0.0,
        "avg_pos_edge": (sum(pos) / len(pos)) if pos else 0.0,
        "avg_neg_edge": (sum(neg) / len(neg)) if neg else 0.0,
        "p10_edge": _quantile(svals, 0.10),
        "p25_edge": _quantile(svals, 0.25),
        "p50_edge": _quantile(svals, 0.50),
        "p75_edge": _quantile(svals, 0.75),
        "p90_edge": _quantile(svals, 0.90),
        "positive_threshold_candidates": {
            "p25_pos": _quantile(spos, 0.25),
            "p50_pos": _quantile(spos, 0.50),
            "p75_pos": _quantile(spos, 0.75),
        },
        "guard_eval": {
            "edge_after_fee_negative": ((total / len(vals)) if vals else 0.0) < 0.0,
            "recommendation": "BLOCK" if (((total / len(vals)) if vals else 0.0) < 0) else "ALLOW_CANDIDATE",
        },
        "histogram": _histogram(vals, bins=20),
    }
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fills_json", type=Path)
    ap.add_argument("--out-json", type=Path, default=None)
    ap.add_argument("--out-txt", type=Path, default=None)
    ap.add_argument("--run-start-ms", type=int, default=None)
    args = ap.parse_args()

    raw = json.loads(args.fills_json.read_text(encoding="utf-8-sig"))
    parsed = _parse_items(raw)
    fills = [f for f in (_as_fill(x) for x in parsed) if f is not None]
    if not fills:
        raise SystemExit("No valid fills")

    now_kst = datetime.now(KST)
    now_ms = int(now_kst.timestamp() * 1000)
    daily_from_ms = _kst_midnight_ms(now_kst)
    first_ms = min(f.ts for f in fills)
    run_from_ms = args.run_start_ms if args.run_start_ms is not None else first_ms

    edges = _build_edges(fills)
    edges_daily = [e for e in edges if int(e["close_ts"]) >= daily_from_ms]
    edges_run = [e for e in edges if int(e["close_ts"]) >= run_from_ms]
    edges_total = edges

    report = {
        "generated_at_kst": now_kst.isoformat(),
        "windows": {
            "daily": {"from_ms": daily_from_ms, "to_ms": now_ms},
            "run": {"from_ms": run_from_ms, "to_ms": now_ms},
            "total": {"from_ms": first_ms, "to_ms": now_ms},
        },
        "source": {
            "fills_path": str(args.fills_json),
            "fills_count": len(fills),
            "matched_chunks_total": len(edges_total),
        },
        "summary": {
            "daily": _summarize_window("DAILY", edges_daily),
            "run": _summarize_window("RUN", edges_run),
            "total": _summarize_window("TOTAL", edges_total),
        },
    }

    d = report["summary"]["daily"]
    r = report["summary"]["run"]
    t = report["summary"]["total"]
    print(f"DAILY_EDGE_AVG={d['avg_edge_after_fee']:.8f} WIN_RATE={d['win_rate']:.4f} GUARD={d['guard_eval']['recommendation']}")
    print(f"RUN_EDGE_AVG={r['avg_edge_after_fee']:.8f} WIN_RATE={r['win_rate']:.4f} GUARD={r['guard_eval']['recommendation']}")
    print(f"TOTAL_EDGE_AVG={t['avg_edge_after_fee']:.8f} WIN_RATE={t['win_rate']:.4f} GUARD={t['guard_eval']['recommendation']}")
    print(f"TOTAL_POS_EDGE_P50={t['positive_threshold_candidates']['p50_pos']:.8f}")
    print("OK")

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.out_txt:
        args.out_txt.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"generated_at_kst={report['generated_at_kst']}",
            f"fills_count={report['source']['fills_count']}",
            f"matched_chunks_total={report['source']['matched_chunks_total']}",
            f"daily.avg_edge_after_fee={d['avg_edge_after_fee']:.8f}",
            f"daily.win_rate={d['win_rate']:.4f}",
            f"daily.guard={d['guard_eval']['recommendation']}",
            f"run.avg_edge_after_fee={r['avg_edge_after_fee']:.8f}",
            f"run.win_rate={r['win_rate']:.4f}",
            f"run.guard={r['guard_eval']['recommendation']}",
            f"total.avg_edge_after_fee={t['avg_edge_after_fee']:.8f}",
            f"total.win_rate={t['win_rate']:.4f}",
            f"total.guard={t['guard_eval']['recommendation']}",
            f"total.pos_edge_p50={t['positive_threshold_candidates']['p50_pos']:.8f}",
        ]
        args.out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
