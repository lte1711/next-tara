import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

KST = timezone(timedelta(hours=9))

EVENT_FILE_DEFAULT = r"C:\projects\NEXT-TRADE\logs\runtime\profitmax_v1_events.jsonl"
OUT_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\pmx"

TRACK_EVENTS = {
    "RUN_START",
    "RUN_END",
    "HEARTBEAT",
    "STRATEGY_BLOCKED",
    "ENTRY",
    "EXIT",
    "SL_COOLDOWN_ARMED",
    "SL_COOLDOWN_RELEASED",
    "ACCOUNT_FAIL",
    "ACCOUNT_OK",
    "QTY_ADJUSTED",
    "RUN_SKIPPED",
    "SL_ORDER_SKIPPED",
}


@dataclass
class ExitAgg:
    total: int = 0
    tp: int = 0
    sl: int = 0
    other: int = 0
    pnl_sum: float = 0.0


@dataclass
class BlockAgg:
    total: int = 0
    reasons: Dict[str, int] = None

    def __post_init__(self):
        if self.reasons is None:
            self.reasons = {}


def parse_ts(ts: str) -> datetime:
    # expects ISO8601 like 2026-03-04T03:39:32.324001+00:00
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def read_events(path: str) -> List[dict]:
    events = []
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # skip bad line
                continue
            et = obj.get("event_type")
            if et in TRACK_EVENTS:
                events.append(obj)
    return events


def pick_symbol(events: List[dict], symbol: Optional[str]) -> str:
    if symbol:
        return symbol
    # infer most frequent non-null symbol
    freq: Dict[str, int] = {}
    for e in events:
        s = e.get("symbol")
        if not s:
            continue
        freq[s] = freq.get(s, 0) + 1
    if not freq:
        return "UNKNOWN"
    return sorted(freq.items(), key=lambda x: x[1], reverse=True)[0][0]


def filter_time(events: List[dict], t0: datetime, t1: datetime, symbol: str) -> List[dict]:
    out = []
    for e in events:
        s = e.get("symbol")
        # keep null-symbol events too (some RUN_START stamps may be null)
        if s and s != symbol:
            continue
        ts = e.get("ts")
        if not ts:
            continue
        dt = parse_ts(ts)
        if t0 <= dt < t1:
            out.append(e)
    return out


def last_n_minutes_range(now_utc: datetime, minutes: int) -> Tuple[datetime, datetime]:
    return now_utc - timedelta(minutes=minutes), now_utc


def kst_midnight_range(now_utc: datetime) -> Tuple[datetime, datetime]:
    now_kst = now_utc.astimezone(KST)
    midnight_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight_kst.astimezone(timezone.utc), now_utc


def top_reasons(reasons: Dict[str, int], topn: int = 5) -> List[Tuple[str, int]]:
    return sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:topn]


def analyze(events: List[dict], symbol: str) -> dict:
    exit_agg = ExitAgg()
    block_agg = BlockAgg()

    entry_count = 0
    hb_count = 0
    account_fail = 0
    last_hb = None
    last_price = None
    last_regime = None
    last_adaptive = None
    last_api_err_streak = None
    last_consecutive_sl = None
    last_session_realized = None
    position_open = None

    for e in events:
        et = e.get("event_type")
        payload = e.get("payload") or {}
        if et == "HEARTBEAT":
            hb_count += 1
            last_hb = e
            last_price = payload.get("price", last_price)
            last_regime = payload.get("regime", last_regime)
            last_adaptive = payload.get("adaptive_regime", last_adaptive)
            last_api_err_streak = payload.get("api_err_streak", last_api_err_streak)
            last_consecutive_sl = payload.get("consecutive_sl", last_consecutive_sl)
            last_session_realized = payload.get("session_realized_pnl", last_session_realized)
            position_open = payload.get("position_open", position_open)

        elif et == "STRATEGY_BLOCKED":
            block_agg.total += 1
            reason = payload.get("reason") or payload.get("block_reason") or "UNKNOWN"
            block_agg.reasons[reason] = block_agg.reasons.get(reason, 0) + 1

        elif et == "ENTRY":
            entry_count += 1

        elif et == "EXIT":
            exit_agg.total += 1
            reason = (payload.get("reason") or "other").lower()
            if reason == "tp":
                exit_agg.tp += 1
            elif reason == "sl":
                exit_agg.sl += 1
            else:
                exit_agg.other += 1
            pnl = payload.get("pnl")
            if isinstance(pnl, (int, float)):
                exit_agg.pnl_sum += float(pnl)

        elif et == "ACCOUNT_FAIL":
            account_fail += 1

    last_hb_ts = parse_ts(last_hb["ts"]).astimezone(KST).isoformat() if last_hb else None

    return {
        "symbol": symbol,
        "heartbeats": hb_count,
        "entries": entry_count,
        "exits_total": exit_agg.total,
        "tp": exit_agg.tp,
        "sl": exit_agg.sl,
        "exit_other": exit_agg.other,
        "pnl_sum": exit_agg.pnl_sum,
        "blocked_total": block_agg.total,
        "blocked_top5": top_reasons(block_agg.reasons, 5),
        "account_fail": account_fail,
        "last": {
            "last_heartbeat_kst": last_hb_ts,
            "price": last_price,
            "regime": last_regime,
            "adaptive_regime": last_adaptive,
            "api_err_streak": last_api_err_streak,
            "consecutive_sl": last_consecutive_sl,
            "session_realized_pnl": last_session_realized,
            "position_open": position_open,
        },
    }


def write_report(out_dir: str, tag: str, report: dict) -> Tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    ts_tag = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    base = f"pmx_auto_{tag}_{ts_tag}"
    json_path = os.path.join(out_dir, base + ".json")
    txt_path = os.path.join(out_dir, base + ".txt")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # human-readable
    lines = []
    lines.append(f"STAMP={base}")
    lines.append(f"SYMBOL={report['symbol']}")
    lines.append("")
    lines.append(
        f"HB={report['heartbeats']} | ENTRY={report['entries']} | EXIT={report['exits_total']} (TP={report['tp']} SL={report['sl']} OTHER={report['exit_other']})"
    )
    lines.append(f"PNL_SUM={report['pnl_sum']}")
    lines.append(f"BLOCKED_TOTAL={report['blocked_total']}")
    if report["blocked_top5"]:
        top = ", ".join([f"{k}:{v}" for k, v in report["blocked_top5"]])
        lines.append(f"BLOCK_TOP5={top}")
    lines.append(f"ACCOUNT_FAIL={report['account_fail']}")
    lines.append("")
    last = report["last"]
    lines.append("LAST_HEARTBEAT_KST=" + str(last.get("last_heartbeat_kst")))
    lines.append("LAST_PRICE=" + str(last.get("price")))
    lines.append("LAST_REGIME=" + str(last.get("regime")))
    lines.append("LAST_ADAPTIVE_REGIME=" + str(last.get("adaptive_regime")))
    lines.append("LAST_API_ERR_STREAK=" + str(last.get("api_err_streak")))
    lines.append("LAST_CONSECUTIVE_SL=" + str(last.get("consecutive_sl")))
    lines.append("LAST_SESSION_REALIZED_PNL=" + str(last.get("session_realized_pnl")))
    lines.append("LAST_POSITION_OPEN=" + str(last.get("position_open")))

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return txt_path, json_path


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=EVENT_FILE_DEFAULT)
    ap.add_argument("--out", default=OUT_DIR_DEFAULT)
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--mode", choices=["lastN", "kst0"], default="kst0")
    args = ap.parse_args()

    all_events = read_events(args.events)
    symbol = pick_symbol(all_events, args.symbol)

    now_utc = datetime.now(timezone.utc)
    if args.mode == "lastN":
        t0, t1 = last_n_minutes_range(now_utc, args.minutes)
        tag = f"last{args.minutes}m"
    else:
        t0, t1 = kst_midnight_range(now_utc)
        tag = "kst0"

    window = filter_time(all_events, t0, t1, symbol)
    report = analyze(window, symbol)
    report["window"] = {
        "mode": args.mode,
        "from_utc": t0.isoformat(),
        "to_utc": t1.isoformat(),
        "minutes": args.minutes if args.mode == "lastN" else None,
    }

    txt_path, json_path = write_report(args.out, tag, report)
    print("REPORT_TXT=" + txt_path)
    print("REPORT_JSON=" + json_path)
    print("FINAL_VERDICT=PASS")


if __name__ == "__main__":
    main()
