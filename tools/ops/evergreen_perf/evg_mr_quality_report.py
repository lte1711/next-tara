import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


PERF_TRADES_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf_trades.jsonl"
OUT_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf"


def _to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _load_latest_regime_map(out_dir: Path) -> Path | None:
    files = sorted(
        out_dir.glob("regime_map_*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def _calc_metrics(pnls: list[float]) -> dict:
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    winrate = (len(wins) / n) if n else 0.0
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0  # negative
    expectancy = (sum(pnls) / n) if n else 0.0
    gross_profit = sum(wins)
    gross_loss_abs = abs(sum(losses))
    if gross_loss_abs > 0:
        pf = gross_profit / gross_loss_abs
    else:
        pf = float("inf") if gross_profit > 0 else 0.0
    # max consecutive losses
    max_streak = 0
    cur = 0
    for p in pnls:
        if p < 0:
            cur += 1
            if cur > max_streak:
                max_streak = cur
        else:
            cur = 0
    return {
        "trades": n,
        "winrate": winrate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy,
        "profit_factor": pf,
        "max_loss_streak": max_streak,
        "gross_profit": gross_profit,
        "gross_loss_abs": gross_loss_abs,
    }


def _max_dd(pnls: list[float]) -> float:
    eq = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        eq += p
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd
    return max_dd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perf_trades", default=PERF_TRADES_DEFAULT)
    ap.add_argument("--out_dir", default=OUT_DIR_DEFAULT)
    ap.add_argument("--regime_map", default="")
    args = ap.parse_args()

    perf_path = Path(args.perf_trades)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    regime_map_path = Path(args.regime_map) if args.regime_map else _load_latest_regime_map(out_dir)
    regime_by_trade: dict[str, str] = {}
    if regime_map_path and regime_map_path.exists():
        with regime_map_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                tid = str(row.get("trade_id") or "")
                if tid:
                    regime_by_trade[tid] = str(row.get("regime_tag") or "UNKNOWN")

    trades = []
    if perf_path.exists():
        with perf_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                tid = str(rec.get("trade_id") or "")
                pnl = _to_float(rec.get("pnl_net", rec.get("realized_pnl", 0.0)), 0.0)
                fee = _to_float(rec.get("fee", 0.0), 0.0)
                signal_id = str(rec.get("signal_id") or "")
                regime = regime_by_trade.get(tid, "UNKNOWN")
                trades.append(
                    {
                        "trade_id": tid,
                        "pnl": pnl,
                        "fee": fee,
                        "signal_id": signal_id,
                        "regime": regime,
                    }
                )

    pnls = [x["pnl"] for x in trades]
    fees_total = sum(x["fee"] for x in trades)
    pnl_net = sum(pnls)
    pnl_gross = pnl_net + fees_total
    overall = _calc_metrics(pnls)
    max_dd = _max_dd(pnls)
    worst_5 = sorted([p for p in pnls if p < 0])[:5]
    largest_win = max([p for p in pnls if p > 0], default=0.0)

    by_regime: dict[str, list[float]] = defaultdict(list)
    for tr in trades:
        by_regime[tr["regime"]].append(tr["pnl"])

    regime_metrics = {}
    for rg in ["RANGE", "TREND", "SHOCK", "UNKNOWN"]:
        vals = by_regime.get(rg, [])
        m = _calc_metrics(vals)
        regime_metrics[rg] = m

    # integrity
    bad_signal = sum(1 for t in trades if t["signal_id"] and t["signal_id"] != "mean_reversion")
    mr_integrity = "PASS" if bad_signal == 0 else "FAIL"

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = out_dir / f"mr_quality_report_{stamp}.txt"

    def pf_str(v):
        return "INF" if v == float("inf") else f"{v:.6f}"

    lines = [
        f"STAMP=MR_QUALITY_{stamp}",
        f"PERF_TRADES={perf_path}",
        f"REGIME_MAP={(str(regime_map_path) if regime_map_path else '')}",
        f"MR_ONLY_INTEGRITY={mr_integrity}",
        f"TRADES={overall['trades']}",
        f"WINRATE={overall['winrate']:.6f}",
        f"AVG_WIN={overall['avg_win']:.8f}",
        f"AVG_LOSS={overall['avg_loss']:.8f}",
        f"EXPECTANCY={overall['expectancy']:.8f}",
        f"PROFIT_FACTOR={pf_str(overall['profit_factor'])}",
        f"MAX_DD={max_dd:.8f}",
        f"MAX_CONSECUTIVE_LOSSES={overall['max_loss_streak']}",
        f"WORST_5_LOSSES={json.dumps(worst_5, ensure_ascii=False)}",
        f"LARGEST_WIN={largest_win:.8f}",
        f"FEES_TOTAL={fees_total:.8f}",
        f"PNL_GROSS={pnl_gross:.8f}",
        f"PNL_NET={pnl_net:.8f}",
        (
            "REGIME_BREAKDOWN="
            + json.dumps(
                {
                    rg: {
                        "trades": regime_metrics[rg]["trades"],
                        "winrate": round(regime_metrics[rg]["winrate"], 6),
                        "expectancy": round(regime_metrics[rg]["expectancy"], 8),
                        "profit_factor": (
                            "INF"
                            if regime_metrics[rg]["profit_factor"] == float("inf")
                            else round(regime_metrics[rg]["profit_factor"], 6)
                        ),
                        "max_loss_streak": regime_metrics[rg]["max_loss_streak"],
                    }
                    for rg in ["RANGE", "TREND", "SHOCK", "UNKNOWN"]
                },
                ensure_ascii=False,
            )
        ),
        "METRIC_DEFINITION=expectancy=mean(trade_pnl_net); profit_factor=sum(win)/abs(sum(loss)); max_dd=peak_to_trough_on_realized_equity",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()

