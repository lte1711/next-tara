import argparse
import json
from datetime import datetime
from pathlib import Path


PERF_TRADES_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf_trades.jsonl"
OUT_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf"


def _pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return (float(part) / float(total)) * 100.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perf_trades", default=PERF_TRADES_DEFAULT)
    ap.add_argument("--out_dir", default=OUT_DIR_DEFAULT)
    ap.add_argument("--tail", type=int, default=30)
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
    rows = rows[-max(1, int(args.tail)) :]

    total = len(rows)
    meta_present = 0
    unknown = 0
    unknown_reason_ok = 0
    table_lines = []
    for r in rows:
        has_meta = all(
            k in r
            for k in [
                "ha_trend_dir",
                "ha_trend_strength",
                "bb_pos",
                "bb_width",
                "bb_squeeze",
                "ha_bb_reason",
                "ha_bb_bar_close_ts",
            ]
        )
        if has_meta:
            meta_present += 1
        is_unknown = (
            str(r.get("ha_trend_dir", "UNKNOWN")).upper() == "UNKNOWN"
            or str(r.get("bb_pos", "UNKNOWN")).upper() == "UNKNOWN"
            or str(r.get("bb_squeeze", "UNKNOWN")).upper() == "UNKNOWN"
        )
        reason = str(r.get("ha_bb_reason") or "").strip()
        if is_unknown:
            unknown += 1
            if reason:
                unknown_reason_ok += 1

        table_lines.append(
            " | ".join(
                [
                    str(r.get("trade_id", "")),
                    str(r.get("ts_entry", "")),
                    str(r.get("ts_exit", "")),
                    f"{float(r.get('pnl_net', r.get('realized_pnl', 0.0))):.8f}",
                    str(r.get("ha_trend_dir", "")),
                    str(r.get("ha_trend_strength", "")),
                    str(r.get("bb_pos", "")),
                    str(r.get("bb_width", "")),
                    str(r.get("bb_squeeze", "")),
                    reason,
                ]
            )
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"ha_bb_signal_snapshot_{stamp}.txt"
    lines = [
        f"STAMP=HA_BB_{stamp}",
        f"SOURCE={perf_path}",
        f"TAIL_TRADES={total}",
        f"HA_BB_META_PRESENT_RATE={_pct(meta_present, total):.2f}%",
        f"UNKNOWN_RATE={_pct(unknown, total):.2f}%",
        f"UNKNOWN_REASON_OK={'YES' if unknown == unknown_reason_ok else 'NO'}",
        "FIELDS=trade_id|ts_entry|ts_exit|pnl_net|ha_trend_dir|ha_trend_strength|bb_pos|bb_width|bb_squeeze|ha_bb_reason",
        "---",
    ]
    lines.extend(table_lines)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()

