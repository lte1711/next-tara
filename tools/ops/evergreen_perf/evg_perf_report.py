import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict


OUT_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf"


def parse_stamp_ts(name: str) -> datetime:
    # perf_aggregate_YYYYMMDD_HHMMSS.(txt/json)
    m = re.search(r"_(\d{8})_(\d{6})", name)
    if not m:
        raise ValueError(f"bad filename: {name}")
    return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")


def load_latest_aggregates(out_dir: Path, since: datetime) -> List[Dict]:
    rows = []
    for p in out_dir.glob("perf_aggregate_*.json"):
        ts = parse_stamp_ts(p.name)
        if ts >= since:
            try:
                rows.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
    rows.sort(key=lambda r: r.get("stamp", ""))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", default=OUT_DIR_DEFAULT)
    ap.add_argument("--mode", choices=["daily", "weekly"], required=True)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    if args.mode == "daily":
        since = now - timedelta(days=1)
        stamp = now.strftime("EVG_DAILY_%Y%m%d_%H%M%S")
        out_txt = out_dir / f"perf_daily_{now.strftime('%Y%m%d_%H%M%S')}.txt"
    else:
        since = now - timedelta(days=7)
        stamp = now.strftime("EVG_WEEKLY_%Y%m%d_%H%M%S")
        out_txt = out_dir / f"perf_weekly_{now.strftime('%Y%m%d_%H%M%S')}.txt"

    rows = load_latest_aggregates(out_dir, since)
    latest = rows[-1] if rows else None

    lines = []
    lines.append(f"STAMP={stamp}")
    lines.append(f"WINDOW_SINCE={since.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"AGG_FILES_IN_WINDOW={len(rows)}")

    if not latest:
        lines.append("STATUS=NO_DATA")
        out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(str(out_txt))
        return

    m = latest.get("metrics", {})
    lines.append("STATUS=OK")
    lines.append(f"TRADES={m.get('trades',0)} WINS={m.get('wins',0)} LOSSES={m.get('losses',0)} WINRATE={m.get('winrate',0):.4f}")
    lines.append(f"TOTAL_PNL={m.get('total_pnl',0):.8f}")
    lines.append(f"MAX_DD={m.get('max_drawdown',0):.8f}")
    lines.append(f"EXPECTANCY={m.get('expectancy',0):.8f}")
    pf = m.get("profit_factor", 0)
    lines.append(f"PROFIT_FACTOR={pf if pf != float('inf') else 'INF'}")

    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out_txt))


if __name__ == "__main__":
    main()
