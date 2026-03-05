from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _parse_iso(ts: str) -> datetime | None:
    try:
        # Handles "...+00:00" and "...Z"
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def load_jsonl(path: Path) -> list[dict[str, Any]]:
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


def latest_stamp(rows: list[dict[str, Any]]) -> str:
    candidates = [str(r.get("stamp", "")) for r in rows if r.get("stamp")]
    return candidates[-1] if candidates else ""


@dataclass
class Metrics:
    stamp: str
    run_start_ts: str | None
    elapsed_sec: int
    exit_total: int
    tp: int
    sl: int
    timeout: int
    strategy_blocked: int
    sl_cooldown_armed: int
    account_fail: int
    api_err_streak_max: int
    session_realized_pnl: float
    vol_bucket_counts: dict[str, int]
    entry_k_avg: float | None
    ha_pass_rate: float | None
    avg_win: float
    avg_loss: float
    win_rate: float
    ev: float
    kill_rule_consecutive_sl2_twice: bool
    kill_rule_pnl_below: bool
    kill_rule_account_fail: bool
    kill_rule_api_err: bool
    kill_rule_no_entry_60m: bool
    kill_rule_same_bucket_4sl: bool
    kill_now: bool


def compute_metrics(rows_all: list[dict[str, Any]], stamp: str, pnl_limit: float) -> Metrics:
    rows = [r for r in rows_all if str(r.get("stamp") or "") == stamp]
    rows.sort(key=lambda r: str(r.get("ts", "")))

    run_start = next((r for r in rows if str(r.get("event_type", "")).upper() == "RUN_START"), None)
    run_start_ts = str(run_start.get("ts")) if run_start else None
    now = datetime.now(timezone.utc)
    start_dt = _parse_iso(run_start_ts) if run_start_ts else None
    elapsed_sec = int((now - start_dt).total_seconds()) if start_dt else 0

    exits = [r for r in rows if str(r.get("event_type", "")).upper() == "EXIT"]
    tps = [r for r in exits if str((r.get("payload") or {}).get("reason", "")).lower() == "tp"]
    sls = [r for r in exits if str((r.get("payload") or {}).get("reason", "")).lower() == "sl"]
    tos = [r for r in exits if str((r.get("payload") or {}).get("reason", "")).lower() == "timeout"]
    blocked = [r for r in rows if str(r.get("event_type", "")).upper() == "STRATEGY_BLOCKED"]
    armed = [r for r in rows if str(r.get("event_type", "")).upper() == "SL_COOLDOWN_ARMED"]
    account_fail = [
        r
        for r in rows
        if str(r.get("event_type", "")).upper() == "ACCOUNT_FAIL"
        or (
            str(r.get("event_type", "")).upper() == "KILL_SWITCH"
            and str(r.get("reason", "")).lower() == "account_check_failed"
        )
    ]
    hbs = [r for r in rows if str(r.get("event_type", "")).upper() == "HEARTBEAT"]
    session_realized_pnl = _safe_float((hbs[-1].get("payload") or {}).get("session_realized_pnl"), 0.0) if hbs else 0.0
    api_err_streak_max = 0
    for hb in hbs:
        api_err_streak_max = max(api_err_streak_max, _safe_int((hb.get("payload") or {}).get("api_err_streak"), 0))

    # Entry-linked maps
    entries = [r for r in rows if str(r.get("event_type", "")).upper() == "ENTRY"]
    trace_to_bucket: dict[str, str] = {}
    trace_to_k: dict[str, float] = {}
    vol_bucket_counts: Counter[str] = Counter()
    entry_ks: list[float] = []

    for e in entries:
        p = e.get("payload") or {}
        trace = str(p.get("trace_id") or "")
        bucket = str(p.get("vol_bucket") or "UNKNOWN").upper()
        k = _safe_float(p.get("entry_k"), 0.0)
        if trace:
            trace_to_bucket[trace] = bucket
            trace_to_k[trace] = k
        vol_bucket_counts[bucket] += 1
        if k > 0:
            entry_ks.append(k)

    entry_k_avg = (sum(entry_ks) / len(entry_ks)) if entry_ks else None

    # HA pass rate (if present)
    ha_total = 0
    ha_pass = 0
    for r in rows:
        p = r.get("payload") or {}
        if isinstance(p, dict):
            # support multiple payload styles
            if "ha_ok" in p:
                ha_total += 1
                ha_pass += 1 if bool(p.get("ha_ok")) else 0
            elif "ha_pass" in p:
                ha_total += 1
                ha_pass += 1 if _safe_int(p.get("ha_pass"), 0) > 0 else 0
    ha_pass_rate = (ha_pass / ha_total) if ha_total > 0 else None

    # EV
    pnl_values = [_safe_float((r.get("payload") or {}).get("pnl"), 0.0) for r in exits]
    wins = [x for x in pnl_values if x > 0]
    losses = [x for x in pnl_values if x < 0]
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (abs(sum(losses) / len(losses))) if losses else 0.0
    win_rate = (len(wins) / len(pnl_values)) if pnl_values else 0.0
    loss_rate = 1.0 - win_rate if pnl_values else 0.0
    ev = (win_rate * avg_win) - (loss_rate * avg_loss)

    # Kill rules
    consec_sl2_events = [r for r in armed if _safe_int((r.get("payload") or {}).get("consecutive_sl"), 0) >= 2]
    kill_rule_consecutive_sl2_twice = len(consec_sl2_events) >= 2
    kill_rule_pnl_below = session_realized_pnl <= pnl_limit
    kill_rule_account_fail = len(account_fail) > 0
    kill_rule_api_err = api_err_streak_max > 0
    kill_rule_no_entry_60m = elapsed_sec >= 3600 and len(entries) == 0

    same_bucket_4sl = False
    streak_bucket = ""
    streak_n = 0
    for r in exits:
        p = r.get("payload") or {}
        if str(p.get("reason", "")).lower() != "sl":
            streak_bucket = ""
            streak_n = 0
            continue
        trace = str(p.get("trace_id") or "")
        bucket = trace_to_bucket.get(trace, str(p.get("vol_bucket") or ""))
        if not bucket:
            streak_bucket = ""
            streak_n = 0
            continue
        if bucket == streak_bucket:
            streak_n += 1
        else:
            streak_bucket = bucket
            streak_n = 1
        if streak_n >= 4:
            same_bucket_4sl = True
            break
    kill_rule_same_bucket_4sl = same_bucket_4sl

    kill_now = any(
        [
            kill_rule_consecutive_sl2_twice,
            kill_rule_pnl_below,
            kill_rule_account_fail,
            kill_rule_api_err,
            kill_rule_no_entry_60m,
            kill_rule_same_bucket_4sl,
        ]
    )

    return Metrics(
        stamp=stamp,
        run_start_ts=run_start_ts,
        elapsed_sec=elapsed_sec,
        exit_total=len(exits),
        tp=len(tps),
        sl=len(sls),
        timeout=len(tos),
        strategy_blocked=len(blocked),
        sl_cooldown_armed=len(armed),
        account_fail=len(account_fail),
        api_err_streak_max=api_err_streak_max,
        session_realized_pnl=session_realized_pnl,
        vol_bucket_counts=dict(vol_bucket_counts),
        entry_k_avg=entry_k_avg,
        ha_pass_rate=ha_pass_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        win_rate=win_rate,
        ev=ev,
        kill_rule_consecutive_sl2_twice=kill_rule_consecutive_sl2_twice,
        kill_rule_pnl_below=kill_rule_pnl_below,
        kill_rule_account_fail=kill_rule_account_fail,
        kill_rule_api_err=kill_rule_api_err,
        kill_rule_no_entry_60m=kill_rule_no_entry_60m,
        kill_rule_same_bucket_4sl=kill_rule_same_bucket_4sl,
        kill_now=kill_now,
    )


def metrics_to_text(m: Metrics) -> str:
    def _pct(v: float | None) -> str:
        return "N/A" if v is None else f"{v * 100:.2f}%"

    lines = [
        "[PMX 003R AUTONOMOUS REPORT]",
        f"stamp: {m.stamp}",
        f"run_start: {m.run_start_ts}",
        f"elapsed_sec: {m.elapsed_sec}",
        f"exit_total: {m.exit_total}",
        f"tp/sl/timeout: {m.tp}/{m.sl}/{m.timeout}",
        f"strategy_blocked: {m.strategy_blocked}",
        f"sl_cooldown_armed: {m.sl_cooldown_armed}",
        f"session_realized_pnl: {m.session_realized_pnl:.6f}",
        f"account_fail: {m.account_fail}",
        f"api_err_streak_max: {m.api_err_streak_max}",
        f"vol_bucket_counts: {json.dumps(m.vol_bucket_counts, ensure_ascii=False)}",
        f"entry_k_avg: {'N/A' if m.entry_k_avg is None else round(m.entry_k_avg, 6)}",
        f"ha_pass_rate: {_pct(m.ha_pass_rate)}",
        f"avg_win: {m.avg_win:.6f}",
        f"avg_loss: {m.avg_loss:.6f}",
        f"win_rate: {m.win_rate:.4f}",
        f"EV: {m.ev:.6f}",
        "[KILL_RULES]",
        f"consecutive_sl2_twice: {m.kill_rule_consecutive_sl2_twice}",
        f"pnl_below_limit: {m.kill_rule_pnl_below}",
        f"account_fail: {m.kill_rule_account_fail}",
        f"api_err_streak: {m.kill_rule_api_err}",
        f"no_entry_60m: {m.kill_rule_no_entry_60m}",
        f"same_bucket_4sl: {m.kill_rule_same_bucket_4sl}",
        f"kill_now: {m.kill_now}",
    ]
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compute PMX 003R autonomous metrics.")
    p.add_argument("--events", default="logs/runtime/profitmax_v1_events.jsonl")
    p.add_argument("--stamp", default="")
    p.add_argument("--pnl-limit", type=float, default=-1.5)
    p.add_argument("--json-out", default="")
    p.add_argument("--text-out", default="")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    events_path = Path(args.events)
    if not events_path.is_absolute():
        events_path = root / events_path
    rows_all = load_jsonl(events_path)
    if not rows_all:
        print("NO_EVENTS")
        return 1

    stamp = args.stamp.strip() or latest_stamp(rows_all)
    if not stamp:
        print("NO_STAMP")
        return 1

    m = compute_metrics(rows_all, stamp=stamp, pnl_limit=args.pnl_limit)
    payload = m.__dict__
    print(json.dumps(payload, ensure_ascii=False))

    if args.json_out:
        out = Path(args.json_out)
        if not out.is_absolute():
            out = root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.text_out:
        out = Path(args.text_out)
        if not out.is_absolute():
            out = root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(metrics_to_text(m), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

