import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime


def parse_ts(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def safe_float(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


def avg(xs):
    return (sum(xs) / len(xs)) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", required=True, help="profitmax_v1_events.jsonl")
    ap.add_argument("--stamp", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cnt = Counter()
    bucket_entry = Counter()
    bucket_k = defaultdict(list)
    bucket_exit = Counter()
    bucket_pnl = defaultdict(float)
    last_pnl = None
    run_start = None
    run_end = None

    with open(args.events, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("stamp") != args.stamp:
                continue

            et = o.get("event_type", "")
            cnt[et] += 1
            payload = o.get("payload") or {}

            if et == "RUN_START":
                run_start = o.get("ts")
            if et == "RUN_END":
                run_end = o.get("ts")

            if et == "HEARTBEAT" and "session_realized_pnl" in payload:
                last_pnl = safe_float(payload.get("session_realized_pnl"))

            if et == "ENTRY":
                b = payload.get("vol_bucket", "NA")
                bucket_entry[b] += 1
                k = payload.get("entry_k")
                if k is not None:
                    bucket_k[b].append(safe_float(k))

            if et == "EXIT":
                b = payload.get("vol_bucket", "NA")
                bucket_exit[b] += 1
                if "pnl" in payload:
                    bucket_pnl[b] += safe_float(payload.get("pnl"))

    lines = []
    lines.append("# PMX 003R 24H FINAL REPORT")
    lines.append(f"- Stamp: `{args.stamp}`")
    lines.append(f"- RUN_START: `{run_start}`")
    lines.append(f"- RUN_END: `{run_end}`")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- ENTRY: **{cnt.get('ENTRY',0)}**")
    lines.append(f"- EXIT: **{cnt.get('EXIT',0)}**")
    lines.append(f"- STRATEGY_BLOCKED: **{cnt.get('STRATEGY_BLOCKED',0)}**")
    lines.append(f"- SL_COOLDOWN_ARMED: **{cnt.get('SL_COOLDOWN_ARMED',0)}**")
    lines.append(f"- STOPPED_EARLY: **{cnt.get('STOPPED_EARLY',0)}**")
    lines.append(f"- session_realized_pnl (last): **{last_pnl}**")
    lines.append("")

    lines.append("## Vol Bucket Breakdown")
    buckets = set(bucket_entry.keys()) | set(bucket_exit.keys())
    for b in sorted(buckets):
        lines.append(
            f"- **{b}**: entry={bucket_entry.get(b,0)}, exit={bucket_exit.get(b,0)}, "
            f"avg_k={avg(bucket_k.get(b,[]))}, pnl_sum={bucket_pnl.get(b,0.0)}"
        )
    lines.append("")
    lines.append("## Notes / Decisions")
    lines.append("- If HIGH bucket contributes positive pnl & LOW bucket losses reduced -> 003R likely improves EV.")
    lines.append("- If entries are rare -> HA filter may be too strict; consider loosening after evidence review.")
    lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()

