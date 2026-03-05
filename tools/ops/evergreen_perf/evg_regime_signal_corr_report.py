import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


PERF_TRADES_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf_trades.jsonl"
OUT_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf"
MIN_SAMPLE_DEFAULT = 30


def _to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _pf(pnls: list[float]) -> float:
    gp = sum(x for x in pnls if x > 0)
    gl = abs(sum(x for x in pnls if x < 0))
    if gl > 0:
        return gp / gl
    return float("inf") if gp > 0 else 0.0


def _max_loss_streak(pnls: list[float]) -> int:
    best = 0
    cur = 0
    for p in pnls:
        if p < 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _max_dd(pnls: list[float]) -> float:
    peak = 0.0
    eq = 0.0
    max_dd = 0.0
    for p in pnls:
        eq += p
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _bb_mode(row: dict) -> str:
    sq = str(row.get("bb_squeeze") or "").upper()
    pos = str(row.get("bb_pos") or "").upper()
    if sq == "YES":
        return "SQUEEZE"
    if pos in {"ABOVE_UPPER", "BELOW_LOWER"}:
        return "BOUNCE"
    if pos in {"ABOVE_MID", "BELOW_MID", "AROUND_MID", "INSIDE"}:
        return "TREND_RIDE"
    return "UNKNOWN"


def _regime(row: dict) -> str:
    rg = str(row.get("regime_tag") or row.get("regime_hint") or "").upper()
    if rg in {"RANGE", "TREND", "SHOCK"}:
        return rg
    return "UNKNOWN"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perf_trades", default=PERF_TRADES_DEFAULT)
    ap.add_argument("--out_dir", default=OUT_DIR_DEFAULT)
    ap.add_argument("--min_sample", type=int, default=MIN_SAMPLE_DEFAULT)
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
                    r = json.loads(line)
                except Exception:
                    continue
                rows.append(r)

    buckets: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    for r in rows:
        key = (
            _regime(r),
            str(r.get("ha_trend_dir") or "UNKNOWN").upper(),
            _bb_mode(r),
            str(r.get("bb_pos") or "UNKNOWN").upper(),
        )
        pnl = _to_float(r.get("pnl_net", r.get("realized_pnl", 0.0)), 0.0)
        buckets[key].append(pnl)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = out_dir / f"regime_signal_corr_{stamp}.txt"
    lines = [
        f"STAMP=REGIME_SIGNAL_CORR_{stamp}",
        f"SOURCE={perf_path}",
        f"TOTAL_TRADES={len(rows)}",
        f"sample_rule=n>={max(1,args.min_sample)}",
        "COLUMNS=regime|ha_dir|bb_mode|bb_pos|n_trades|winrate|expectancy|profit_factor|max_dd|max_loss_streak|insufficient_sample",
        "---",
    ]
    for key in sorted(buckets.keys()):
        pnls = buckets[key]
        n = len(pnls)
        wins = sum(1 for p in pnls if p > 0)
        wr = (wins / n) if n else 0.0
        exp = (sum(pnls) / n) if n else 0.0
        pf = _pf(pnls)
        mdd = _max_dd(pnls)
        streak = _max_loss_streak(pnls)
        insufficient = "YES" if n < max(1, args.min_sample) else "NO"
        pf_text = "INF" if pf == float("inf") else f"{pf:.6f}"
        lines.append(
            f"{key[0]}|{key[1]}|{key[2]}|{key[3]}|{n}|{wr:.6f}|{exp:.8f}|{pf_text}|{mdd:.8f}|{streak}|{insufficient}"
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()

