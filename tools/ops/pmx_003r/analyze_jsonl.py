import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime


def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


def parse_ts(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stamp", default="")
    args = ap.parse_args()

    events = []
    with open(args.jsonl, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
                events.append(o)
            except Exception:
                continue

    cnt = Counter()
    bucket_cnt = Counter()
    bucket_pnl = defaultdict(float)
    bucket_tp = Counter()
    bucket_sl = Counter()
    k_values = []
    ha_tf_seen = Counter()

    api_err_max = 0
    account_fail = 0
    last_hb_pnl = None
    last_entry_ts = None
    last_exit_ts = None

    for o in events:
        et = o.get("event_type", "")
        cnt[et] += 1

        payload = o.get("payload") or {}
        api_err = payload.get("api_err_streak")
        if api_err is not None:
            api_err_max = max(api_err_max, safe_int(api_err))

        if et in ("ACCOUNT_FAIL", "account_check_failed"):
            account_fail += 1

        if et == "HEARTBEAT":
            if "session_realized_pnl" in payload:
                last_hb_pnl = safe_float(payload.get("session_realized_pnl"))

        if et == "ENTRY":
            b = payload.get("vol_bucket", "NA")
            bucket_cnt[b] += 1
            k = payload.get("entry_k")
            if k is not None:
                k_values.append(safe_float(k, 0.0))
            ha_h = payload.get("ha_higher_tf")
            ha_e = payload.get("ha_entry_tf")
            if ha_h:
                ha_tf_seen[f"ha_higher_tf={ha_h}"] += 1
            if ha_e:
                ha_tf_seen[f"ha_entry_tf={ha_e}"] += 1
            ts = parse_ts(o.get("ts", ""))
            if ts:
                last_entry_ts = ts

        if et == "EXIT":
            reason = payload.get("reason", "")
            b = payload.get("vol_bucket", "NA")
            if reason == "TP":
                bucket_tp[b] += 1
            if reason == "SL":
                bucket_sl[b] += 1
            if "pnl" in payload:
                bucket_pnl[b] += safe_float(payload.get("pnl"))
            ts = parse_ts(o.get("ts", ""))
            if ts:
                last_exit_ts = ts

    exit_total = cnt.get("EXIT", 0)
    avg_pnl_per_exit = (last_hb_pnl / exit_total) if (last_hb_pnl is not None and exit_total > 0) else None
    k_avg = (sum(k_values) / len(k_values)) if k_values else None

    lines = []
    lines.append("# PMX 003R Auto Summary")
    if args.stamp:
        lines.append(f"- Stamp: `{args.stamp}`")
    lines.append("")
    lines.append("## Fact Counters")
    lines.append(f"- ENTRY: **{cnt.get('ENTRY',0)}**")
    lines.append(f"- EXIT: **{cnt.get('EXIT',0)}**")
    lines.append(f"- HEARTBEAT: **{cnt.get('HEARTBEAT',0)}**")
    lines.append(f"- STRATEGY_BLOCKED: **{cnt.get('STRATEGY_BLOCKED',0)}**")
    lines.append(f"- SL_COOLDOWN_ARMED: **{cnt.get('SL_COOLDOWN_ARMED',0)}**")
    lines.append(f"- STOPPED_EARLY: **{cnt.get('STOPPED_EARLY',0)}**")
    lines.append(f"- ACCOUNT_FAIL: **{account_fail}**")
    lines.append(f"- API_ERR_STREAK_MAX: **{api_err_max}**")
    lines.append("")

    lines.append("## 003R Marker Coverage")
    lines.append(f"- vol_bucket seen in ENTRY: **{sum(bucket_cnt.values())}**")
    lines.append(f"- entry_k samples: **{len(k_values)}**")
    lines.append(f"- ha_tf markers: **{sum(ha_tf_seen.values())}**")
    lines.append("")

    lines.append("## Vol Bucket Distribution (ENTRY)")
    for b, v in bucket_cnt.most_common():
        lines.append(f"- {b}: {v}")
    lines.append("")

    lines.append("## HA TF Observations")
    for k, v in ha_tf_seen.most_common():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## PnL Snapshot")
    lines.append(f"- last session_realized_pnl (from HEARTBEAT): **{last_hb_pnl}**")
    lines.append(f"- avg pnl per EXIT (rough): **{avg_pnl_per_exit}**")
    lines.append(f"- avg entry_k: **{k_avg}**")
    lines.append("")
    lines.append("## Timing")
    lines.append(f"- last ENTRY ts: {last_entry_ts}")
    lines.append(f"- last EXIT ts: {last_exit_ts}")
    lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()

