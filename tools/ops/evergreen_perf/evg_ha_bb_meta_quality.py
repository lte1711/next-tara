import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


PERF_TRADES_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf_trades.jsonl"
OUT_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf"
VALID_UNKNOWN_REASONS = {
    "no_ohlc_source",
    "insufficient_bars",
    "bar_not_closed",
    "calc_error",
}


def _pct(a: int, b: int) -> float:
    if b <= 0:
        return 0.0
    return (float(a) / float(b)) * 100.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perf_trades", default=PERF_TRADES_DEFAULT)
    ap.add_argument("--out_dir", default=OUT_DIR_DEFAULT)
    args = ap.parse_args()

    perf_path = Path(args.perf_trades)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    if perf_path.exists():
        with perf_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue

    total = len(rows)
    meta_present = 0
    unknown = 0
    unknown_reason_ok = 0
    reason_counts = Counter()

    for r in rows:
        has_meta = all(
            k in r
            for k in (
                "tf",
                "ha_trend_dir",
                "ha_trend_strength",
                "bb_pos",
                "bb_width",
                "bb_squeeze",
                "ha_bb_reason",
                "ha_bb_bar_close_ts",
            )
        )
        if has_meta:
            meta_present += 1
        is_unknown = (
            str(r.get("ha_trend_dir") or "").upper() == "UNKNOWN"
            or str(r.get("bb_pos") or "").upper() == "UNKNOWN"
            or str(r.get("bb_squeeze") or "").upper() == "UNKNOWN"
        )
        reason = str(r.get("ha_bb_reason") or "").strip()
        if is_unknown:
            unknown += 1
            reason_counts[reason or ""] += 1
            if reason in VALID_UNKNOWN_REASONS:
                unknown_reason_ok += 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = out_dir / f"ha_bb_meta_quality_{stamp}.txt"
    lines = [
        f"STAMP=HA_BB_META_QUALITY_{stamp}",
        f"SOURCE={perf_path}",
        f"TOTAL_TRADES={total}",
        f"META_PRESENT_RATE={_pct(meta_present, total):.2f}%",
        f"UNKNOWN_RATE={_pct(unknown, total):.2f}%",
        f"UNKNOWN_REASON_OK={'YES' if unknown == unknown_reason_ok else 'NO'}",
        f"UNKNOWN_REASON_BREAKDOWN={json.dumps(dict(reason_counts), ensure_ascii=False)}",
        f"VALID_UNKNOWN_REASONS={json.dumps(sorted(VALID_UNKNOWN_REASONS), ensure_ascii=False)}",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()

