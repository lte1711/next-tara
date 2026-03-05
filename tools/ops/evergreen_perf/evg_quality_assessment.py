import argparse
import json
from datetime import datetime
from pathlib import Path


PERF_TRADES_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf_trades.jsonl"
OUT_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf"


def _to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def compute_max_dd(equity_curve):
    peak = float("-inf")
    max_dd = 0.0
    for x in equity_curve:
        if x > peak:
            peak = x
        dd = peak - x
        if dd > max_dd:
            max_dd = dd
    return max_dd


def max_consecutive_losses(pnls):
    best = 0
    cur = 0
    for p in pnls:
        if p < 0:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perf_trades", default=PERF_TRADES_DEFAULT)
    ap.add_argument("--out_dir", default=OUT_DIR_DEFAULT)
    args = ap.parse_args()

    perf_path = Path(args.perf_trades)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    trades = []
    if perf_path.exists():
        with perf_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                pnl = _to_float(obj.get("realized_pnl"), None)
                if pnl is None:
                    continue
                trades.append(pnl)

    n = len(trades)
    wins = sum(1 for p in trades if p > 0)
    losses = sum(1 for p in trades if p < 0)
    winrate = (wins / n) if n else 0.0

    avg_win = (sum(p for p in trades if p > 0) / wins) if wins else 0.0
    avg_loss_abs = (abs(sum(p for p in trades if p < 0)) / losses) if losses else 0.0
    expectancy = (winrate * avg_win) - ((1 - winrate) * avg_loss_abs) if n else 0.0

    gross_profit = sum(p for p in trades if p > 0)
    gross_loss_abs = abs(sum(p for p in trades if p < 0))
    if gross_loss_abs > 0:
        profit_factor = gross_profit / gross_loss_abs
    else:
        profit_factor = float("inf") if gross_profit > 0 else 0.0

    equity = [0.0]
    for p in trades:
        equity.append(equity[-1] + p)
    total_pnl = equity[-1] if equity else 0.0
    max_dd = compute_max_dd(equity) if len(equity) > 1 else 0.0
    max_loss_streak = max_consecutive_losses(trades)
    ruin_proxy = "HIGH" if max_loss_streak >= 6 else ("MED" if max_loss_streak >= 4 else "LOW")

    status = "OK"
    if expectancy <= 0 and profit_factor < 1.0:
        status = "STOP"
    elif max_loss_streak >= 4 or (abs(total_pnl) > 0 and max_dd >= abs(total_pnl) * 0.8):
        status = "WARN"

    notes = f"risk_of_ruin_proxy={ruin_proxy}; source={perf_path}"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_txt = out_dir / f"quality_assessment_{ts}.txt"
    lines = [
        f"STAMP=QUALITY_{ts}",
        f"TRADES={n}",
        f"WINRATE={winrate:.6f}",
        f"AVG_WIN={avg_win:.8f}",
        f"AVG_LOSS_ABS={avg_loss_abs:.8f}",
        f"EXPECTANCY={expectancy:.8f}",
        f"PROFIT_FACTOR={profit_factor if profit_factor != float('inf') else 'INF'}",
        f"TOTAL_PNL={total_pnl:.8f}",
        f"MAX_DD={max_dd:.8f}",
        f"MAX_CONSECUTIVE_LOSSES={max_loss_streak}",
        f"STATUS={status}",
        f"NOTES={notes}",
    ]
    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out_txt))


if __name__ == "__main__":
    main()
