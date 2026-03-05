from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze SL cooldown enriched diagnostics.")
    p.add_argument(
        "--events",
        default="logs/runtime/profitmax_v1_events.jsonl",
        help="Path to profitmax events JSONL.",
    )
    p.add_argument(
        "--out-dir",
        default="evidence/pmx",
        help="Directory for output report.",
    )
    p.add_argument(
        "--stamp",
        default="",
        help="Optional PMX stamp. If provided, prefer events matching this stamp and name output with stamp.",
    )
    return p.parse_args()


def load_events(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def seq_loop_count(events: list[dict[str, Any]]) -> int:
    seq: list[str] = []
    for ev in events:
        et = str(ev.get("event_type", "")).upper()
        if et in {"EXIT", "SL_COOLDOWN_ARMED", "SL_COOLDOWN_RELEASED"}:
            seq.append(et)
    needle = ["EXIT", "SL_COOLDOWN_ARMED", "SL_COOLDOWN_RELEASED", "EXIT", "SL_COOLDOWN_ARMED"]
    if len(seq) < len(needle):
        return 0
    n = 0
    for i in range(0, len(seq) - len(needle) + 1):
        if seq[i : i + len(needle)] == needle:
            n += 1
    return n


def safe_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    events_path = Path(args.events)
    if not events_path.is_absolute():
        events_path = root / events_path
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    events_all = load_events(events_path)
    events = events_all
    stamp = args.stamp.strip()
    if stamp:
        filtered = [e for e in events_all if str(e.get("stamp") or "") == stamp]
        if filtered:
            events = filtered
    sl_armed = [e for e in events if str(e.get("event_type", "")).upper() == "SL_COOLDOWN_ARMED"]

    basis = Counter()
    symbol_side = Counter()
    filled_fields = Counter()
    unknown_fields = Counter()
    px_changes: list[float] = []
    cooldown_vals: list[float] = []

    required_fields = [
        "sl_basis",
        "sl_count_session",
        "entry_id",
        "symbol",
        "side",
        "qty",
        "entry_price",
        "exit_price",
        "mark_price_at_exit",
        "pnl_realized",
        "pnl_unrealized",
        "fee_total",
        "cooldown_minutes",
        "max_consecutive_sl",
        "cooldown_until_ts",
        "last_order_ts",
        "last_fill_ts",
        "price_context",
        "volatility_state",
    ]

    for e in sl_armed:
        payload = e.get("payload", {}) if isinstance(e.get("payload"), dict) else {}
        sl_basis = str(payload.get("sl_basis", "unknown")).lower()
        basis[sl_basis] += 1

        sym = str(payload.get("symbol", e.get("symbol", "unknown")))
        side = str(payload.get("side", "unknown"))
        symbol_side[f"{sym}:{side}"] += 1

        for k in required_fields:
            v = payload.get(k)
            if v is None or (isinstance(v, str) and v.lower() == "unknown"):
                unknown_fields[k] += 1
            else:
                filled_fields[k] += 1

        ep = safe_float(payload.get("entry_price"))
        xp = safe_float(payload.get("exit_price"))
        if ep and ep != 0 and xp:
            px_changes.append((xp - ep) / ep * 100.0)

        cd = safe_float(payload.get("cooldown_minutes"))
        if cd is not None:
            cooldown_vals.append(cd)

    loop_n = seq_loop_count(events)
    now = datetime.now().strftime("%Y%m%d_%H%M")
    suffix = stamp if stamp else now
    out_path = out_dir / f"sl_cooldown_enriched_report_{suffix}.txt"

    lines: list[str] = []
    lines.append("SL COOLDOWN ENRICHED DIAGNOSTIC REPORT")
    lines.append(f"events_path={events_path}")
    lines.append(f"total_events={len(events)}")
    if stamp:
        lines.append(f"stamp={stamp}")
        lines.append(f"stamp_filtered_events={len(events)} / raw_events={len(events_all)}")
    lines.append(f"sl_cooldown_armed_events={len(sl_armed)}")
    lines.append("")

    lines.append("[sl_basis ratio]")
    total_basis = sum(basis.values()) or 1
    for k, v in basis.most_common():
        lines.append(f"- {k}: {v} ({(v / total_basis) * 100:.1f}%)")
    if not basis:
        lines.append("- no sl_cooldown_armed events")
    lines.append("")

    lines.append("[price change around SL exit]")
    if px_changes:
        avg_change = sum(px_changes) / len(px_changes)
        lines.append(f"- samples={len(px_changes)}")
        lines.append(f"- avg_pct={avg_change:.4f}")
        lines.append(f"- min_pct={min(px_changes):.4f}")
        lines.append(f"- max_pct={max(px_changes):.4f}")
    else:
        lines.append("- no entry/exit price samples")
    lines.append("")

    lines.append("[cooldown loop]")
    lines.append(f"- loop_pattern_count={loop_n}")
    if cooldown_vals:
        lines.append(f"- cooldown_minutes_values={sorted(set(int(x) for x in cooldown_vals))}")
    lines.append("")

    lines.append("[symbol/side top5]")
    for k, v in symbol_side.most_common(5):
        lines.append(f"- {k}: {v}")
    if not symbol_side:
        lines.append("- no symbol/side samples")
    lines.append("")

    lines.append("[field coverage]")
    for k in required_fields:
        f = filled_fields.get(k, 0)
        u = unknown_fields.get(k, 0)
        lines.append(f"- {k}: filled={f}, unknown_or_null={u}")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
