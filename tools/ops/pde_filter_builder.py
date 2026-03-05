#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDE Filter Builder
- Input: pde_report_*.json from pde_edge_analyzer.py
- Output: threshold sweep table + recommended threshold(s)

Goal:
- Improve win rate / edge avg by filtering out "bad edges" based on edge_after_fee
- Provide coverage vs quality tradeoff

Robust parsing:
- Accepts different report shapes:
  A) report["daily"]["edges"] = [float, ...]
  B) report["daily"]["trades"] = [{"edge":..} or {"edge_after_fee":..}, ...]
  C) report["daily_edges"] = [...]
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

KST = timezone(timedelta(hours=9))

WINDOW_KEYS = ["daily", "run", "total"]


def _now_kst() -> str:
    return datetime.now(KST).isoformat()


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def _first_present(d: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    for k in keys:
        if k in d:
            return d[k]
    return None


def _extract_edges_from_obj(obj: Any) -> List[float]:
    """
    Accept:
      - list of floats
      - list of dicts with edge fields
      - dict with "edges"/"trades"
    """
    edges: List[float] = []

    if obj is None:
        return edges

    if isinstance(obj, list):
        # list[float] or list[dict]
        for it in obj:
            if isinstance(it, (int, float)):
                v = _to_float(it)
                if v is not None:
                    edges.append(v)
            elif isinstance(it, dict):
                v = _to_float(_first_present(it, ["edge_after_fee", "edge", "edge_net", "edge_post_fee"]))
                if v is not None:
                    edges.append(v)
        return edges

    if isinstance(obj, dict):
        # common patterns: {"edges":[...]} or {"trades":[...]}
        if "edges" in obj:
            edges.extend(_extract_edges_from_obj(obj["edges"]))
        if "trades" in obj:
            edges.extend(_extract_edges_from_obj(obj["trades"]))
        # sometimes nested like {"edge_distribution":{"edges":[...]}}
        ed = _first_present(obj, ["edge_distribution", "distribution", "hist", "histogram"])
        if isinstance(ed, dict):
            maybe_edges = _first_present(ed, ["edges", "values", "samples"])
            edges.extend(_extract_edges_from_obj(maybe_edges))
        return edges

    return edges


def extract_window_edges(report: Dict[str, Any], window: str) -> List[float]:
    """
    Try multiple locations for each window:
      report[window] -> edges/trades
      report[f"{window}_edges"] -> list
      report["edges"][window] -> list
    """
    edges: List[float] = []

    if window in report and isinstance(report[window], (dict, list)):
        edges.extend(_extract_edges_from_obj(report[window]))

    alt = f"{window}_edges"
    if alt in report:
        edges.extend(_extract_edges_from_obj(report[alt]))

    if "edges" in report and isinstance(report["edges"], dict) and window in report["edges"]:
        edges.extend(_extract_edges_from_obj(report["edges"][window]))

    # de-dupe while preserving order (float exact de-dupe is fine here)
    seen = set()
    out: List[float] = []
    for v in edges:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def percentile(values: List[float], p: float) -> Optional[float]:
    if not values:
        return None
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    xs = sorted(values)
    k = (len(xs) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return xs[int(k)]
    d0 = xs[f] * (c - k)
    d1 = xs[c] * (k - f)
    return d0 + d1


@dataclass
class SweepRow:
    threshold: float
    coverage: float
    count: int
    win_rate: float
    edge_avg: float
    edge_p50: float


def sweep_thresholds(edges: List[float], thresholds: List[float]) -> List[SweepRow]:
    rows: List[SweepRow] = []
    n = len(edges)
    if n == 0:
        return rows

    for t in thresholds:
        kept = [e for e in edges if e >= t]
        k = len(kept)
        if k == 0:
            rows.append(SweepRow(threshold=t, coverage=0.0, count=0, win_rate=0.0, edge_avg=0.0, edge_p50=0.0))
            continue

        wins = sum(1 for e in kept if e > 0)
        win_rate = wins / k
        edge_avg = sum(kept) / k
        p50 = percentile(kept, 50) or 0.0
        rows.append(SweepRow(
            threshold=t,
            coverage=k / n,
            count=k,
            win_rate=win_rate,
            edge_avg=edge_avg,
            edge_p50=p50,
        ))
    return rows


def build_threshold_grid(edges: List[float], mode: str) -> List[float]:
    """
    mode:
      - "fixed": 0.00 .. 0.30 step 0.01
      - "percentile": thresholds from P0..P95 (step 5) of all edges
      - "hybrid": union of fixed + percentile-derived, unique sorted
    """
    if not edges:
        return [0.0]

    if mode == "fixed":
        return [round(i / 100.0, 2) for i in range(0, 31)]  # 0.00..0.30

    if mode == "percentile":
        ps = list(range(0, 100, 5))  # 0..95
        ts = []
        for p in ps:
            v = percentile(edges, p)
            if v is not None:
                ts.append(float(v))
        # unique sorted
        return sorted(set(ts))

    # hybrid default
    fixed = [round(i / 100.0, 2) for i in range(0, 31)]
    ps = list(range(0, 100, 5))
    pct = []
    for p in ps:
        v = percentile(edges, p)
        if v is not None:
            pct.append(float(v))
    return sorted(set(fixed + pct))


def recommend(rows: List[SweepRow], min_win_rate: float, min_edge_avg: float) -> Optional[SweepRow]:
    """
    Pick the row that satisfies constraints with maximum coverage.
    Tie-breaker: higher edge_avg.
    """
    candidates = [r for r in rows if r.count > 0 and r.win_rate >= min_win_rate and r.edge_avg >= min_edge_avg]
    if not candidates:
        return None
    candidates.sort(key=lambda r: (r.coverage, r.edge_avg), reverse=True)
    return candidates[0]


def fmt_rows(rows: List[SweepRow], top_n: int = 12) -> str:
    # show best by edge_avg and best by coverage among constraint-satisfiers will be printed separately
    lines = []
    lines.append("threshold\tcoverage\tcount\twin_rate\tedge_avg\tedge_p50")
    for r in rows[:top_n]:
        lines.append(f"{r.threshold:.6f}\t{r.coverage:.4f}\t{r.count}\t{r.win_rate:.4f}\t{r.edge_avg:.8f}\t{r.edge_p50:.8f}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pde_report_json", help="Path to pde_report_*.json from pde_edge_analyzer")
    ap.add_argument("--mode", choices=["hybrid", "fixed", "percentile"], default="hybrid")
    ap.add_argument("--min-win-rate", type=float, default=0.45)
    ap.add_argument("--min-edge-avg", type=float, default=0.00)
    ap.add_argument("--out", default=None, help="Output JSON path")
    args = ap.parse_args()

    in_path = Path(args.pde_report_json).expanduser()
    report = json.loads(in_path.read_text(encoding="utf-8-sig"))

    out: Dict[str, Any] = {
        "generated_at_kst": _now_kst(),
        "input": str(in_path),
        "params": {
            "mode": args.mode,
            "min_win_rate": args.min_win_rate,
            "min_edge_avg": args.min_edge_avg,
        },
        "windows": {},
        "notes": {
            "meaning": "Filter keeps trades with edge_after_fee >= threshold. Metrics computed on kept set.",
        },
    }

    # Console header
    print(f"INPUT = {in_path}")
    print(f"MODE = {args.mode} | min_win_rate={args.min_win_rate} | min_edge_avg={args.min_edge_avg}")
    print("")

    for w in WINDOW_KEYS:
        edges = extract_window_edges(report, w)
        n = len(edges)
        if n == 0:
            out["windows"][w] = {"count": 0, "error": "no edges found for window"}
            print(f"[{w.upper()}] edges=0 (skip)")
            print("")
            continue

        thresholds = build_threshold_grid(edges, args.mode)
        rows = sweep_thresholds(edges, thresholds)

        # also compute baseline stats
        base_win = sum(1 for e in edges if e > 0) / n
        base_avg = sum(edges) / n
        base_p50 = percentile(edges, 50) or 0.0

        # recommend
        rec = recommend(rows, args.min_win_rate, args.min_edge_avg)

        # store
        out_rows = [{
            "threshold": r.threshold,
            "coverage": r.coverage,
            "count": r.count,
            "win_rate": r.win_rate,
            "edge_avg": r.edge_avg,
            "edge_p50": r.edge_p50,
        } for r in rows]

        out["windows"][w] = {
            "base": {"count": n, "win_rate": base_win, "edge_avg": base_avg, "edge_p50": base_p50},
            "recommendation": ({
                "threshold": rec.threshold,
                "coverage": rec.coverage,
                "count": rec.count,
                "win_rate": rec.win_rate,
                "edge_avg": rec.edge_avg,
                "edge_p50": rec.edge_p50,
            } if rec else None),
            "sweep": out_rows,
        }

        # Console summary
        print(f"[{w.upper()}] base_count={n} base_win_rate={base_win:.4f} base_edge_avg={base_avg:.8f} base_p50={base_p50:.8f}")

        if rec:
            print(f"[{w.upper()}] RECOMMEND threshold={rec.threshold:.6f} coverage={rec.coverage:.4f} "
                  f"win_rate={rec.win_rate:.4f} edge_avg={rec.edge_avg:.8f} edge_p50={rec.edge_p50:.8f}")
        else:
            print(f"[{w.upper()}] RECOMMEND = NONE (no threshold satisfies constraints)")

        # Print top 12 by coverage (already in threshold order; show highest-coverage satisfying constraints and the first 12 rows)
        # For readability: show first 12 thresholds only
        print("SAMPLE (first 12 rows):")
        print(fmt_rows(rows[:12], top_n=12))
        print("")

    if args.out:
        out_path = Path(args.out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"OUT = {out_path}")

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
