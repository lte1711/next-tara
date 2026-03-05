import json
import re
import sys
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def _norm(s: str) -> str:
    return (s or "").replace("\r\n", "\n")


def extract_json_candidates(text: str) -> List[str]:
    cands: List[str] = []
    t = _norm(text)

    # Snapshot files usually have one JSON payload per line.
    for line in t.split("\n"):
        s = line.strip()
        if len(s) < 2:
            continue
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            cands.append(s)

    # Fallback wide candidates if line payloads are not cleanly split.
    for m in re.finditer(r"\{[\s\S]{20,}\}", t):
        cands.append(m.group(0))
    for m in re.finditer(r"\[[\s\S]{20,}\]", t):
        cands.append(m.group(0))

    return cands[:300]


def try_parse_json(cands: List[str]) -> List[Any]:
    parsed: List[Any] = []
    seen: set[str] = set()
    for s in cands:
        s2 = re.sub(r"[\x00-\x1f]+$", "", s.strip())
        if not s2 or s2 in seen:
            continue
        try:
            parsed.append(json.loads(s2))
            seen.add(s2)
        except Exception:
            continue
    return parsed


def pick_objects(objs: List[Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Returns (ops_health, profitmax_status, ledger_pnl, orders_payload).
    """
    ops = None
    pmx = None
    pnl = None
    orders = None

    for o in objs:
        if not isinstance(o, dict):
            continue
        keys = {str(k) for k in o.keys()}
        kblob = " ".join(sorted(keys)).lower()
        blob = json.dumps(o, ensure_ascii=False).lower()

        if ops is None and (
            "contract_version" in keys
            or "health_status" in blob
            or "checkpoint_status" in blob
            or ("status" in keys and "capabilities" in keys)
        ):
            ops = o
            continue

        if pmx is None and ("summary" in keys or "events" in keys):
            pmx = o
            continue

        if orders is None and ("items" in keys and isinstance(o.get("items"), list)) and ("count" in keys or "next" in keys):
            orders = o
            continue

        if pnl is None and (
            "realized_pnl" in keys
            or "unrealized_pnl" in keys
            or "equity" in keys
            or "pnl" in kblob
            or "drawdown" in kblob
        ):
            pnl = o
            continue

    return ops, pmx, pnl, orders


def deep_find_numbers(obj: Any, key_hints: List[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}

    def walk(x: Any, path: str = ""):
        if isinstance(x, dict):
            for k, v in x.items():
                k2 = str(k)
                p2 = f"{path}.{k2}" if path else k2
                lk = k2.lower()
                if any(h in lk for h in key_hints):
                    if isinstance(v, (int, float)):
                        out[p2] = float(v)
                    elif isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v.strip()):
                        out[p2] = float(v.strip())
                walk(v, p2)
        elif isinstance(x, list):
            for i, v in enumerate(x[:300]):
                walk(v, f"{path}[{i}]")

    walk(obj)
    return out


# --- v1.1 ADDITIONS (additive-only) -----------------------------------------
def extract_section(text: str, header_candidates: List[str], max_lines: int = 80) -> str:
    """
    Find the first matching header line and return the following max_lines lines as a section window.
    """
    t = _norm(text)
    lines = t.split("\n")
    header_re = re.compile("|".join([re.escape(h) for h in header_candidates]), re.IGNORECASE)

    for i, line in enumerate(lines):
        if header_re.search(line):
            start = i
            end = min(len(lines), i + 1 + max_lines)
            return "\n".join(lines[start:end])
    return ""


def extract_int(text: str, patterns: List[str]) -> Optional[int]:
    """
    Try multiple regex patterns; return the first captured int.
    Patterns must contain exactly one capturing group for the number.
    """
    t = _norm(text)
    for pat in patterns:
        m = re.search(pat, t, re.IGNORECASE | re.MULTILINE)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
    return None


def extract_normalized_int(snapshot_text: str, key: str) -> Optional[int]:
    return extract_int(snapshot_text, patterns=[rf"^\s*{re.escape(key)}\s*=\s*(\d+)\s*$"])


def extract_orders_fills(snapshot_text: str) -> Dict[str, Optional[int]]:
    """
    Extract orders_count and fills_count from snapshot text with multi-pattern fallback.
    """
    t = _norm(snapshot_text)
    orders_sec = extract_section(t, ["Orders", "ORDERS", "Open Orders", "Order List"], max_lines=120)
    fills_sec = extract_section(t, ["Fills", "FILLS", "Trades", "Trade History"], max_lines=120)

    orders_count = extract_int(
        orders_sec or t,
        patterns=[
            r"orders_count\s*[:=]\s*(\d+)",
            r"\borders\s*[:=]\s*(\d+)",
            r"Orders?\s*Count\s*[:=]?\s*(\d+)",
            r"\bOPEN\s*ORDERS?\b.*?(\d+)",
        ],
    )

    fills_count = extract_int(
        fills_sec or t,
        patterns=[
            r"fills_count\s*[:=]\s*(\d+)",
            r"\bfills\s*[:=]\s*(\d+)",
            r"Fills?\s*Count\s*[:=]?\s*(\d+)",
            r"\bTRADES?\b.*?(\d+)",
        ],
    )

    return {"orders_count": orders_count, "fills_count": fills_count}


def extract_blocked_count(snapshot_text: str) -> Optional[int]:
    t = _norm(snapshot_text)
    direct = extract_int(
        t,
        patterns=[
            r"blocked_count\s*[:=]\s*(\d+)",
        ],
    )
    if direct is not None:
        return direct
    events = re.findall(r'"event_type"\s*:\s*"STRATEGY_BLOCKED"', t, re.IGNORECASE)
    return len(events) if events else None


def extract_s001_blocked(snapshot_text: str) -> Optional[int]:
    """
    Extract S001 blocked count from snapshot text.
    """
    t = _norm(snapshot_text)
    direct = extract_int(
        t,
        patterns=[
            r"BLOCKED[_\-\s]*S001[_\-\s]*COUNT\s*[:=]\s*(\d+)",
            r"\bS001\b.*?\bBLOCKED\b.*?[:=]\s*(\d+)",
            r"Surgery[-\s]*001.*?(?:count|COUNT)?\s*[:=]?\s*(\d+)",
        ],
    )
    if direct is not None:
        return direct

    # Fallback: count blocked S001 event lines in JSON text.
    blocked_events = re.findall(r'"code"\s*:\s*"S001"[\s\S]{0,120}?"action"\s*:\s*"blocked"', t, re.IGNORECASE)
    if blocked_events:
        return len(blocked_events)
    return None


def extract_ev(snapshot_text: str) -> Optional[int]:
    """
    EV (Event Volume):
    1) explicit EV=... if present
    2) count non-header lines in event section
    """
    t = _norm(snapshot_text)
    # v1.2 normalized block first
    ev_norm = extract_normalized_int(t, "ev")
    if ev_norm is not None:
        return ev_norm
    ev_total = extract_normalized_int(t, "events_total")
    if ev_total is not None:
        return ev_total

    ev = extract_int(t, patterns=[r"\bEV\b\s*[:=]\s*(\d+)"])
    if ev is not None:
        return ev

    ev_sec = extract_section(t, ["Recent Events", "Events", "Event Stream", "Audit"], max_lines=250)
    if not ev_sec:
        return None

    lines = [ln.strip() for ln in ev_sec.split("\n")]
    lines = [ln for ln in lines if ln and not re.search(r"recent events|event stream|audit", ln, re.IGNORECASE)]
    lines = [ln for ln in lines if not re.search(r"\b(ts|time|type|event|trace)\b", ln, re.IGNORECASE)]
    return len(lines)


def merge_v11_metrics(base: Dict[str, Any], snapshot_text: str) -> Dict[str, Any]:
    """
    Attach v1.1 metrics to existing parsed snapshot dict (additive-only).
    """
    # v1.2 normalized block has highest priority.
    ord_norm = extract_normalized_int(snapshot_text, "orders_count")
    open_norm = extract_normalized_int(snapshot_text, "open_orders_count")
    canceled_norm = extract_normalized_int(snapshot_text, "canceled_count")
    rejected_norm = extract_normalized_int(snapshot_text, "rejected_count")
    blocked_norm = extract_normalized_int(snapshot_text, "blocked_count")
    fill_norm = extract_normalized_int(snapshot_text, "fills_count")
    s001_norm = extract_normalized_int(snapshot_text, "s001_blocked")
    ev_norm = extract_normalized_int(snapshot_text, "ev")
    ev_total_norm = extract_normalized_int(snapshot_text, "events_total")

    of = extract_orders_fills(snapshot_text)
    base["orders_count"] = ord_norm if ord_norm is not None else of["orders_count"]
    base["open_orders_count"] = open_norm
    base["canceled_count"] = canceled_norm
    base["rejected_count"] = rejected_norm
    base["blocked_count"] = blocked_norm if blocked_norm is not None else extract_blocked_count(snapshot_text)
    base["fills_count"] = fill_norm if fill_norm is not None else of["fills_count"]
    base["s001_blocked"] = s001_norm if s001_norm is not None else extract_s001_blocked(snapshot_text)
    base["ev"] = ev_norm if ev_norm is not None else (ev_total_norm if ev_total_norm is not None else extract_ev(snapshot_text))
    return base


# --- END v1.1 ADDITIONS -----------------------------------------------------


def delta_int(a: Optional[int], b: Optional[int]) -> Optional[int]:
    if a is None or b is None:
        return None
    return b - a


def first_int_from_paths(d: Dict[str, float], preferred: List[str]) -> Optional[int]:
    for pref in preferred:
        for k, v in d.items():
            if pref in k.lower():
                try:
                    return int(v)
                except Exception:
                    continue
    return None


def count_order_statuses(orders_payload: Optional[Dict[str, Any]]) -> Dict[str, Optional[int]]:
    if not orders_payload:
        return {"open_orders_count": None, "canceled_count": None, "rejected_count": None}
    items = orders_payload.get("items")
    if not isinstance(items, list):
        return {"open_orders_count": None, "canceled_count": None, "rejected_count": None}

    open_count = 0
    canceled = 0
    rejected = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        st = str(it.get("status", "")).upper()
        if st in ("NEW", "PARTIALLY_FILLED"):
            open_count += 1
        elif st == "CANCELED":
            canceled += 1
        elif st == "REJECTED":
            rejected += 1
    return {
        "open_orders_count": open_count,
        "canceled_count": canceled,
        "rejected_count": rejected,
    }


@dataclass
class Snapshot:
    path: Path
    raw_text: str
    ops: Optional[Dict[str, Any]]
    pmx: Optional[Dict[str, Any]]
    pnl: Optional[Dict[str, Any]]
    orders_payload: Optional[Dict[str, Any]]
    orders_count: Optional[int]
    open_orders_count: Optional[int]
    canceled_count: Optional[int]
    rejected_count: Optional[int]
    blocked_count: Optional[int]
    fills_count: Optional[int]
    max_order_ts: Optional[int]
    max_fill_ts: Optional[int]
    s001_blocked: Optional[int]
    ev: Optional[int]
    ha_filter_eval_count: Optional[int]
    ha_filter_pass_count: Optional[int]
    ha_filter_skip_count: Optional[int]
    pmx_nums: Dict[str, float]
    pnl_nums: Dict[str, float]


def load_snapshot(path: Path) -> Snapshot:
    text = read_text(path)
    cands = extract_json_candidates(text)
    objs = try_parse_json(cands)
    ops, pmx, pnl, orders_payload = pick_objects(objs)

    pmx_nums = deep_find_numbers(pmx, ["blocked", "fills", "orders", "throttle", "cooldown", "kill", "downgrade", "s001"]) if pmx else {}
    pnl_nums = deep_find_numbers(pnl, ["pnl", "equity", "balance", "drawdown", "unreal", "real"]) if pnl else {}

    parsed: Dict[str, Any] = {
        "orders_count": None,
        "open_orders_count": None,
        "canceled_count": None,
        "rejected_count": None,
        "blocked_count": None,
        "fills_count": None,
        "max_order_ts": None,
        "max_fill_ts": None,
        "s001_blocked": None,
        "ev": None,
        "ha_filter_eval_count": None,
        "ha_filter_pass_count": None,
        "ha_filter_skip_count": None,
    }
    parsed = merge_v11_metrics(parsed, text)
    parsed["max_order_ts"] = extract_normalized_int(text, "max_order_ts")
    parsed["max_fill_ts"] = extract_normalized_int(text, "max_fill_ts")
    parsed["ha_filter_eval_count"] = extract_normalized_int(text, "ha_filter_eval_count")
    parsed["ha_filter_pass_count"] = extract_normalized_int(text, "ha_filter_pass_count")
    parsed["ha_filter_skip_count"] = extract_normalized_int(text, "ha_filter_skip_count")

    # Structured overrides from parsed JSON payloads if text regex missed.
    if orders_payload is not None:
        if parsed["orders_count"] is None:
            if isinstance(orders_payload.get("count"), int):
                parsed["orders_count"] = int(orders_payload["count"])
            elif isinstance(orders_payload.get("items"), list):
                parsed["orders_count"] = len(orders_payload["items"])
        status_counts = count_order_statuses(orders_payload)
        if parsed["open_orders_count"] is None:
            parsed["open_orders_count"] = status_counts["open_orders_count"]
        if parsed["canceled_count"] is None:
            parsed["canceled_count"] = status_counts["canceled_count"]
        if parsed["rejected_count"] is None:
            parsed["rejected_count"] = status_counts["rejected_count"]

    if pmx is not None:
        if parsed["fills_count"] is None:
            parsed["fills_count"] = first_int_from_paths(
                pmx_nums,
                preferred=["summary.fills", "fills_count", "fills", "recent_fills"],
            )
        if parsed["s001_blocked"] is None:
            parsed["s001_blocked"] = first_int_from_paths(
                pmx_nums,
                preferred=["s001", "blocked"],
            )
        if parsed["blocked_count"] is None:
            parsed["blocked_count"] = first_int_from_paths(
                pmx_nums,
                preferred=["strategy_blocked", "blocked"],
            )
        if parsed["ev"] is None and isinstance(pmx.get("events"), list):
            parsed["ev"] = len(pmx.get("events") or [])
        elif isinstance(parsed["ev"], int) and parsed["ev"] == 0 and isinstance(pmx.get("events"), list):
            # Event section regex can undercount to zero on JSON-line snapshots; prefer explicit events length.
            parsed["ev"] = len(pmx.get("events") or [])

    # Numeric lock for v1.1 requested counters.
    if parsed["fills_count"] is None:
        parsed["fills_count"] = 0
    if parsed["s001_blocked"] is None:
        parsed["s001_blocked"] = 0
    if parsed["ev"] is None:
        parsed["ev"] = 0

    return Snapshot(
        path=path,
        raw_text=text,
        ops=ops,
        pmx=pmx,
        pnl=pnl,
        orders_payload=orders_payload,
        orders_count=parsed["orders_count"],
        open_orders_count=parsed["open_orders_count"],
        canceled_count=parsed["canceled_count"],
        rejected_count=parsed["rejected_count"],
        blocked_count=parsed["blocked_count"],
        fills_count=parsed["fills_count"],
        max_order_ts=parsed["max_order_ts"],
        max_fill_ts=parsed["max_fill_ts"],
        s001_blocked=parsed["s001_blocked"],
        ev=parsed["ev"],
        ha_filter_eval_count=parsed["ha_filter_eval_count"],
        ha_filter_pass_count=parsed["ha_filter_pass_count"],
        ha_filter_skip_count=parsed["ha_filter_skip_count"],
        pmx_nums=pmx_nums,
        pnl_nums=pnl_nums,
    )


def diff_numbers(a: Dict[str, float], b: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k in sorted(set(a.keys()) | set(b.keys())):
        if k in a and k in b:
            out[k] = b[k] - a[k]
    return out


def build_warnings(report: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    for delta_key in ["delta_start_to_mid", "delta_start_to_end"]:
        d = report.get(delta_key) or {}
        if d.get("orders_count_delta") is not None and d["orders_count_delta"] < 0:
            warnings.append(f"{delta_key}: orders_count_delta is negative (possible session mismatch)")
        if d.get("open_orders_count_delta") is not None and d["open_orders_count_delta"] < 0:
            warnings.append(f"{delta_key}: open_orders_count_delta is negative (possible session mismatch)")
        if d.get("canceled_count_delta") is not None and d["canceled_count_delta"] < 0:
            warnings.append(f"{delta_key}: canceled_count_delta is negative (possible session mismatch)")
        if d.get("rejected_count_delta") is not None and d["rejected_count_delta"] < 0:
            warnings.append(f"{delta_key}: rejected_count_delta is negative (possible session mismatch)")
        if d.get("blocked_count_delta") is not None and d["blocked_count_delta"] < 0:
            warnings.append(f"{delta_key}: blocked_count_delta is negative (possible session mismatch)")
        if d.get("fills_count_delta") is not None and d["fills_count_delta"] < 0:
            warnings.append(f"{delta_key}: fills_count_delta is negative (possible session mismatch)")
        if d.get("ev_delta") is not None and d["ev_delta"] < 0:
            warnings.append(f"{delta_key}: ev_delta is negative (possible session mismatch)")
        if d.get("ha_filter_pass_delta") is not None and d["ha_filter_pass_delta"] < 0:
            warnings.append(f"{delta_key}: ha_filter_pass_delta is negative (possible session mismatch)")
        if d.get("ha_filter_skip_delta") is not None and d["ha_filter_skip_delta"] < 0:
            warnings.append(f"{delta_key}: ha_filter_skip_delta is negative (possible session mismatch)")
        if d.get("ha_filter_eval_delta") is not None and d["ha_filter_eval_delta"] < 0:
            warnings.append(f"{delta_key}: ha_filter_eval_delta is negative (possible session mismatch)")
        ms = d.get("missing_start_fields") or []
        if ms:
            warnings.append(f"{delta_key}: missing_start_fields={','.join(ms)}")
    return warnings


def generate_summary_report(analysis: Dict[str, Any], output_path: Path) -> None:
    start = analysis.get("start", {})
    end = analysis.get("end", analysis.get("mid", {}))
    dse = analysis.get("delta_start_to_end", analysis.get("delta_start_to_mid", {}))
    warnings = analysis.get("warnings", [])

    orders_delta = dse.get("orders_count_delta")
    open_orders_delta = dse.get("open_orders_count_delta")
    canceled_delta = dse.get("canceled_count_delta")
    rejected_delta = dse.get("rejected_count_delta")
    blocked_delta = dse.get("blocked_count_delta")
    fills_delta = dse.get("fills_count_delta")
    max_order_ts_delta = dse.get("max_order_ts_delta")
    max_fill_ts_delta = dse.get("max_fill_ts_delta")
    ev_delta = dse.get("ev_delta")
    s001_delta = dse.get("s001_blocked_delta")
    ha_eval_delta = dse.get("ha_filter_eval_delta")
    ha_pass_delta = dse.get("ha_filter_pass_delta")
    ha_skip_delta = dse.get("ha_filter_skip_delta")

    lines: List[str] = []
    lines.append("PMX SESSION SUMMARY")
    lines.append(f"STAMP: {Path(str(start.get('file', ''))).stem.replace('session_start_', '')}")
    lines.append(f"DURATION: {start.get('file', '-') } -> {end.get('file', '-')}")
    lines.append("")
    lines.append(f"Orders Delta: {orders_delta}")
    lines.append(f"Open Orders Delta: {open_orders_delta}")
    lines.append(f"Canceled Delta: {canceled_delta}")
    lines.append(f"Rejected Delta: {rejected_delta}")
    lines.append(f"Blocked Delta: {blocked_delta}")
    lines.append(f"Fills Delta: {fills_delta}")
    lines.append(f"Order TS Delta: {max_order_ts_delta}")
    lines.append(f"Fill TS Delta: {max_fill_ts_delta}")
    lines.append(f"Events Delta: {ev_delta}")
    lines.append(f"HA Filter Eval Delta: {ha_eval_delta}")
    lines.append(f"HA Filter Pass Delta: {ha_pass_delta}")
    lines.append(f"HA Filter Skip Delta: {ha_skip_delta}")
    lines.append("")

    insights: List[str] = []
    if fills_delta == 0 and isinstance(orders_delta, int) and orders_delta > 0 and isinstance(open_orders_delta, int) and open_orders_delta > 0:
        insights.append("Unfilled accumulation: orders and open orders increased while fills stayed flat.")
    elif fills_delta == 0 and isinstance(orders_delta, int) and orders_delta > 0:
        insights.append("Orders increased but fills did not increase.")
    if isinstance(canceled_delta, int) and canceled_delta > 0:
        insights.append("Cancel loop risk: canceled orders increased.")
    if isinstance(rejected_delta, int) and rejected_delta > 0:
        insights.append("Rejection/limit signal: rejected orders increased.")
    if isinstance(blocked_delta, int) and blocked_delta > 0:
        insights.append("Gate impact: blocked events increased.")
    if isinstance(ha_eval_delta, int) and ha_eval_delta > 0:
        insights.append("HA filter evaluated entries during this session.")
    if isinstance(ha_skip_delta, int) and ha_skip_delta > 0:
        insights.append("HA filter suppressed entries during this session.")
    if isinstance(ha_pass_delta, int) and ha_pass_delta > 0:
        insights.append("HA filter passed entry conditions during this session.")
    if isinstance(s001_delta, int) and s001_delta > 0:
        insights.append("S001 blocked count increased.")
    if isinstance(dse.get("pmx_num_deltas"), dict) and any("kill" in k.lower() and v != 0 for k, v in dse["pmx_num_deltas"].items()):
        insights.append("Kill-state change detected.")
    if isinstance(ev_delta, int) and ev_delta > 200:
        insights.append("High activity event session.")
    if not insights:
        if isinstance(max_order_ts_delta, int) and max_order_ts_delta > 0:
            insights.append("New order timestamp detected (ts-based), even if count delta is flat.")
        elif isinstance(max_fill_ts_delta, int) and max_fill_ts_delta > 0:
            insights.append("New fill timestamp detected (ts-based), even if count delta is flat.")
        else:
            insights.append("No notable signal.")

    lines.append("INSIGHTS:")
    for i in insights:
        lines.append(f"- {i}")

    lines.append("")
    lines.append("WARNINGS:")
    if warnings:
        for w in warnings:
            lines.append(f"- {w}")
    else:
        lines.append("- none")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("session_start", nargs="?")
    parser.add_argument("session_mid", nargs="?")
    parser.add_argument("session_end", nargs="?")
    parser.add_argument("--stamp", dest="stamp", default=None)
    parser.add_argument("--summary-out", dest="summary_out", default=None)
    args = parser.parse_args()

    if args.stamp:
        root = Path("evidence/pmx")
        p_start = root / f"session_start_{args.stamp}.txt"
        p_mid = root / f"session_mid_15m_{args.stamp}.txt"
        p_end = root / f"session_end_60m_{args.stamp}.txt"
        if not p_start.exists():
            print(f"ERROR: missing start snapshot for stamp={args.stamp}: {p_start}")
            return 2
        if not p_mid.exists():
            print(f"ERROR: missing mid snapshot for stamp={args.stamp}: {p_mid}")
            return 2
        if not p_end.exists():
            p_end = None
        if not args.summary_out:
            args.summary_out = str(root / f"analysis_{args.stamp}_summary.txt")
    else:
        if not args.session_start or not args.session_mid:
            parser.error("session_start and session_mid are required unless --stamp is provided")
        p_start = Path(args.session_start)
        p_mid = Path(args.session_mid)
        p_end = Path(args.session_end) if args.session_end else None

    s0 = load_snapshot(p_start)
    s1 = load_snapshot(p_mid)
    s2 = load_snapshot(p_end) if p_end else None

    def summarize(s: Snapshot) -> Dict[str, Any]:
        return {
            "file": str(s.path),
            "orders_count": s.orders_count,
            "open_orders_count": s.open_orders_count,
            "canceled_count": s.canceled_count,
            "rejected_count": s.rejected_count,
            "blocked_count": s.blocked_count,
            "fills_count": s.fills_count,
            "max_order_ts": s.max_order_ts,
            "max_fill_ts": s.max_fill_ts,
            "s001_blocked": s.s001_blocked,
            "ev": s.ev,
            "ha_filter_eval_count": s.ha_filter_eval_count,
            "ha_filter_pass_count": s.ha_filter_pass_count,
            "ha_filter_skip_count": s.ha_filter_skip_count,
            "pmx_numeric_keys_found": len(s.pmx_nums),
            "pnl_numeric_keys_found": len(s.pnl_nums),
            "pmx_nums_sample": dict(list(s.pmx_nums.items())[:10]),
            "pnl_nums_sample": dict(list(s.pnl_nums.items())[:10]),
        }

    report: Dict[str, Any] = {
        "start": summarize(s0),
        "mid": summarize(s1),
    }

    missing_start_fields = [
        name
        for name, v in {
            "orders_count": s0.orders_count,
            "open_orders_count": s0.open_orders_count,
            "canceled_count": s0.canceled_count,
            "rejected_count": s0.rejected_count,
            "blocked_count": s0.blocked_count,
            "fills_count": s0.fills_count,
            "max_order_ts": s0.max_order_ts,
            "max_fill_ts": s0.max_fill_ts,
            "s001_blocked": s0.s001_blocked,
            "ev": s0.ev,
            "ha_filter_eval_count": s0.ha_filter_eval_count,
            "ha_filter_pass_count": s0.ha_filter_pass_count,
            "ha_filter_skip_count": s0.ha_filter_skip_count,
        }.items()
        if v is None
    ]

    report["delta_start_to_mid"] = {
        "orders_count_delta": delta_int(s0.orders_count, s1.orders_count),
        "open_orders_count_delta": delta_int(s0.open_orders_count, s1.open_orders_count),
        "canceled_count_delta": delta_int(s0.canceled_count, s1.canceled_count),
        "rejected_count_delta": delta_int(s0.rejected_count, s1.rejected_count),
        "blocked_count_delta": delta_int(s0.blocked_count, s1.blocked_count),
        "fills_count_delta": delta_int(s0.fills_count, s1.fills_count),
        "max_order_ts_delta": delta_int(s0.max_order_ts, s1.max_order_ts),
        "max_fill_ts_delta": delta_int(s0.max_fill_ts, s1.max_fill_ts),
        "s001_blocked_delta": delta_int(s0.s001_blocked, s1.s001_blocked),
        "ev_delta": delta_int(s0.ev, s1.ev),
        "ha_filter_eval_delta": delta_int(s0.ha_filter_eval_count, s1.ha_filter_eval_count),
        "ha_filter_pass_delta": delta_int(s0.ha_filter_pass_count, s1.ha_filter_pass_count),
        "ha_filter_skip_delta": delta_int(s0.ha_filter_skip_count, s1.ha_filter_skip_count),
        "pmx_num_deltas": diff_numbers(s0.pmx_nums, s1.pmx_nums),
        "pnl_num_deltas": diff_numbers(s0.pnl_nums, s1.pnl_nums),
        "missing_start_fields": missing_start_fields,
    }

    if s2:
        report["end"] = summarize(s2)
        report["delta_start_to_end"] = {
            "orders_count_delta": delta_int(s0.orders_count, s2.orders_count),
            "open_orders_count_delta": delta_int(s0.open_orders_count, s2.open_orders_count),
            "canceled_count_delta": delta_int(s0.canceled_count, s2.canceled_count),
            "rejected_count_delta": delta_int(s0.rejected_count, s2.rejected_count),
            "blocked_count_delta": delta_int(s0.blocked_count, s2.blocked_count),
            "fills_count_delta": delta_int(s0.fills_count, s2.fills_count),
            "max_order_ts_delta": delta_int(s0.max_order_ts, s2.max_order_ts),
            "max_fill_ts_delta": delta_int(s0.max_fill_ts, s2.max_fill_ts),
            "s001_blocked_delta": delta_int(s0.s001_blocked, s2.s001_blocked),
            "ev_delta": delta_int(s0.ev, s2.ev),
            "ha_filter_eval_delta": delta_int(s0.ha_filter_eval_count, s2.ha_filter_eval_count),
            "ha_filter_pass_delta": delta_int(s0.ha_filter_pass_count, s2.ha_filter_pass_count),
            "ha_filter_skip_delta": delta_int(s0.ha_filter_skip_count, s2.ha_filter_skip_count),
            "pmx_num_deltas": diff_numbers(s0.pmx_nums, s2.pmx_nums),
            "pnl_num_deltas": diff_numbers(s0.pnl_nums, s2.pnl_nums),
            "missing_start_fields": missing_start_fields,
        }

        if (
            report["delta_start_to_end"]["s001_blocked_delta"] is not None
            and report["delta_start_to_end"]["s001_blocked_delta"] > 0
            and any("kill" in k.lower() and v > 0 for k, v in report["delta_start_to_end"]["pmx_num_deltas"].items())
        ):
            report["insight"] = "S001 blocked increase and kill-state change co-occurred; possible blocked->kill escalation."

    # PnL key explain fields to clarify empty delta cases.
    k0 = sorted(s0.pnl_nums.keys())
    k1 = sorted(s1.pnl_nums.keys())
    k2 = sorted(s2.pnl_nums.keys()) if s2 else []
    kunion = sorted(set(k0) | set(k1) | set(k2))
    report["explain"] = {
        "pnl_keys_start": k0,
        "pnl_keys_mid": k1,
        "pnl_keys_end": k2,
        "pnl_keys_union": kunion,
        "pnl_keys_missing_in_start": sorted(set(kunion) - set(k0)),
    }
    report["warnings"] = build_warnings(report)

    if args.summary_out:
        generate_summary_report(report, Path(args.summary_out))

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
