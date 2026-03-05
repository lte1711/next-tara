import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


PERF_TRADES_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf_trades.jsonl"
OUT_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf"


def _to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _metrics(pnls: list[float]) -> dict:
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    wr = (len(wins) / n) if n else 0.0
    exp = (sum(pnls) / n) if n else 0.0
    gp = sum(wins)
    gl = abs(sum(losses))
    pf = (gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0)
    eq = 0.0
    peak = 0.0
    mdd = 0.0
    streak = 0
    best = 0
    for p in pnls:
        eq += p
        if eq > peak:
            peak = eq
        mdd = max(mdd, peak - eq)
        if p < 0:
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    return {
        "trades": n,
        "winrate": wr,
        "expectancy": exp,
        "profit_factor": pf,
        "max_dd": mdd,
        "max_loss_streak": best,
    }


def _is_ha_opposite(side: str, ha_dir: str) -> bool:
    side_u = (side or "").upper()
    dir_u = (ha_dir or "").upper()
    if side_u == "LONG" and dir_u == "DOWN":
        return True
    if side_u == "SHORT" and dir_u == "UP":
        return True
    return False


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
                    r = json.loads(line)
                except Exception:
                    continue
                rows.append(r)

    base_pnls = []
    sim_pnls = []
    skipped = 0
    reasons = Counter()

    for r in rows:
        signal_id = str(r.get("signal_id") or "")
        pnl = _to_float(r.get("pnl_net", r.get("realized_pnl", 0.0)), 0.0)
        side = str(r.get("side") or "")
        ha_dir = str(r.get("ha_trend_dir") or "UNKNOWN")

        base_pnls.append(pnl)
        if signal_id != "mean_reversion":
            sim_pnls.append(pnl)
            continue

        if _is_ha_opposite(side, ha_dir):
            skipped += 1
            reasons["ha_opposite_dir"] += 1
            continue

        sim_pnls.append(pnl)

    base = _metrics(base_pnls)
    sim = _metrics(sim_pnls)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = out_dir / f"mr_guard_sim_{stamp}.txt"
    pf_base = "INF" if base["profit_factor"] == float("inf") else f"{base['profit_factor']:.6f}"
    pf_sim = "INF" if sim["profit_factor"] == float("inf") else f"{sim['profit_factor']:.6f}"
    lines = [
        f"STAMP=MR_GUARD_SIM_{stamp}",
        f"SOURCE={perf_path}",
        "RULE=skip MR trades if HA direction is opposite to side (offline simulation only)",
        f"BASE_trades={base['trades']} BASE_winrate={base['winrate']:.6f} BASE_expectancy={base['expectancy']:.8f} BASE_profit_factor={pf_base} BASE_max_dd={base['max_dd']:.8f} BASE_max_loss_streak={base['max_loss_streak']}",
        f"SIM_trades={sim['trades']} SIM_winrate={sim['winrate']:.6f} SIM_expectancy={sim['expectancy']:.8f} SIM_profit_factor={pf_sim} SIM_max_dd={sim['max_dd']:.8f} SIM_max_loss_streak={sim['max_loss_streak']}",
        f"skipped_trades_count={skipped}",
        f"skipped_reason_breakdown={json.dumps(dict(reasons), ensure_ascii=False)}",
        "EXECUTION_IMPACT=NONE (no live order path touched)",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()

