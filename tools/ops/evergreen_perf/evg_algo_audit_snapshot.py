import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen


EVENTS_DEFAULT = r"C:\projects\NEXT-TRADE\logs\runtime\profitmax_v1_events.jsonl"
OUT_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf"


def parse_iso_ts(v):
    if not isinstance(v, str):
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except Exception:
        return None


def fetch_json(url):
    try:
        with urlopen(url, timeout=10) as r:
            raw = r.read().decode("utf-8", errors="ignore")
            return json.loads(raw), None
    except Exception as e:
        return None, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=EVENTS_DEFAULT)
    ap.add_argument("--out_dir", default=OUT_DIR_DEFAULT)
    ap.add_argument("--hours", type=int, default=24)
    args = ap.parse_args()

    events_path = Path(args.events)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=args.hours)

    counts = Counter()
    blocked_reasons = Counter()
    run_end = 0
    stopped_early = 0
    account_fail = 0
    total_scanned = 0

    if events_path.exists():
        with events_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                total_scanned += 1
                et = str(obj.get("event_type") or obj.get("type") or "").upper()
                ts = parse_iso_ts(obj.get("ts"))
                if ts is not None and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts is not None and ts < since:
                    continue

                if et in {"ENTRY", "EXIT", "TP", "SL"}:
                    counts[et] += 1

                if "BLOCKED" in et:
                    counts["BLOCKED"] += 1
                    payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
                    reason = str(payload.get("reason") or obj.get("reason") or et)
                    blocked_reasons[reason] += 1

                if et == "RUN_END":
                    run_end += 1
                if et == "STOPPED_EARLY":
                    stopped_early += 1
                if et == "ACCOUNT_FAIL":
                    account_fail += 1

    open_orders, open_orders_err = fetch_json("http://127.0.0.1:8100/api/v1/trading/open_orders")
    positions, positions_err = fetch_json("http://127.0.0.1:8100/api/v1/trading/positions")
    health, health_err = fetch_json("http://127.0.0.1:8100/api/v1/ops/health")

    open_orders_count = -1
    if isinstance(open_orders, dict):
        open_orders_count = int(open_orders.get("count", 0))

    positions_nonzero = -1
    if isinstance(positions, dict):
        items = positions.get("items", [])
        nonzero = 0
        for it in items if isinstance(items, list) else []:
            try:
                qty = float(it.get("positionAmt", it.get("qty", 0)))
            except Exception:
                qty = 0.0
            if abs(qty) > 0:
                nonzero += 1
        positions_nonzero = nonzero

    health_status = "UNKNOWN"
    if isinstance(health, dict):
        health_status = str(health.get("status", "UNKNOWN"))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = out_dir / f"algo_audit_{ts}.txt"
    lines = [
        f"STAMP=ALGO_AUDIT_{ts}",
        f"WINDOW_HOURS={args.hours}",
        f"EVENTS_FILE={events_path}",
        f"EVENTS_SCANNED={total_scanned}",
        f"ENTRY={counts.get('ENTRY',0)} EXIT={counts.get('EXIT',0)} TP={counts.get('TP',0)} SL={counts.get('SL',0)} BLOCKED={counts.get('BLOCKED',0)}",
        f"BLOCKED_REASON_TOP5={json.dumps(blocked_reasons.most_common(5), ensure_ascii=False)}",
        f"RUN_END={run_end} STOPPED_EARLY={stopped_early} ACCOUNT_FAIL={account_fail}",
        f"OPEN_ORDERS_COUNT={open_orders_count}",
        f"POSITIONS_NONZERO={positions_nonzero}",
        f"HEALTH_STATUS={health_status}",
        f"OPEN_ORDERS_ERR={open_orders_err or ''}",
        f"POSITIONS_ERR={positions_err or ''}",
        f"HEALTH_ERR={health_err or ''}",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()
