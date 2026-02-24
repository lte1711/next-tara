#!/usr/bin/env python3
"""Minimal live_obs producer for local ops_web testing.

Writes a one-line JSON metrics payload to metrics/live_obs.jsonl every second.
If the existing file appears "dirty" (missing expected keys), rotates it.
"""
import json
import time
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
METRICS_DIR = BASE_DIR / "metrics"
METRICS_DIR.mkdir(parents=True, exist_ok=True)

OUT = METRICS_DIR / "live_obs.jsonl"

def rollover_if_dirty(path: Path):
    if not path.exists():
        return
    try:
        tail = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-5:]
        ok = 0
        for ln in tail:
            try:
                obj = json.loads(ln)
                if isinstance(obj, dict) and ("event_queue_depth" in obj or "ws_messages_total" in obj):
                    ok += 1
            except Exception:
                continue
        if ok >= 1:
            return
    except Exception:
        pass

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_name(f"live_obs_{ts}.jsonl")
    try:
        path.rename(bak)
    except Exception:
        # best-effort
        pass

def main():
    rollover_if_dirty(OUT)

    start = time.time()
    ticks = 0
    ws_messages_total = 0
    event_published = 0
    event_consumed = 0
    event_queue_depth_max = 0

    print(f"[live_obs_mvp] writing -> {OUT}")
    try:
        while True:
            now = time.time()
            ticks += 1

            # MVP behavior: deterministic increments
            ws_messages_total += 2
            event_published += 1
            event_consumed += 1

            event_queue_depth = max(0, event_published - event_consumed)
            event_queue_depth_max = max(event_queue_depth_max, event_queue_depth)

            row = {
                "ts": now,
                "elapsed_sec": round(now - start, 3),
                "ticks": ticks,
                "ws_messages_total": ws_messages_total,
                "event_published": event_published,
                "event_consumed": event_consumed,
                "event_queue_depth": event_queue_depth,
                "event_queue_depth_max_seen": event_queue_depth_max,
                "ledger_global_pnl": 0.0,
                "ledger_peak_pnl": 0.0,
                "ledger_worst_dd": 0.0,
            }

            with OUT.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

            time.sleep(1)
    except KeyboardInterrupt:
        print("[live_obs_mvp] stopped by user")


if __name__ == "__main__":
    main()
