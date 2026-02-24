from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .data_binance import ms_to_iso


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_outputs(
    out_dir: Path,
    params: dict[str, Any],
    metrics: dict[str, Any],
    trades: list[dict[str, Any]],
    equity_curve: list[dict[str, Any]],
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    params_path = out_dir / "params.json"
    metrics_path = out_dir / "metrics.json"
    trades_path = out_dir / "trades.csv"
    equity_path = out_dir / "equity_curve.csv"
    report_path = out_dir / "report.md"

    _write_json(params_path, params)
    _write_json(metrics_path, metrics)

    trade_rows = []
    for t in trades:
        trade_rows.append(
            {
                **t,
                "entry_time_iso": ms_to_iso(int(t["entry_time"])),
                "exit_time_iso": ms_to_iso(int(t["exit_time"])),
            }
        )
    _write_csv(
        trades_path,
        trade_rows,
        [
            "entry_time",
            "exit_time",
            "entry_time_iso",
            "exit_time_iso",
            "side",
            "entry_price",
            "exit_price",
            "qty",
            "gross_pnl",
            "fee",
            "net_pnl",
            "reason",
        ],
    )

    equity_rows = [{**e, "time_iso": ms_to_iso(int(e["time"]))} for e in equity_curve]
    _write_csv(equity_path, equity_rows, ["time", "time_iso", "equity"])

    report = f"""# PHASE-S1 Backtest Report

- Symbol: `{metrics['symbol']}`
- Timeframe: `{metrics['timeframe']}`
- Total Trades: `{metrics['total_trades']}`
- Win Rate: `{metrics['win_rate']:.4f}`
- Gross PnL: `{metrics['gross_pnl']}`
- Net PnL: `{metrics['net_pnl']}`
- Avg Win: `{metrics['avg_win']}`
- Avg Loss: `{metrics['avg_loss']}`
- RR: `{metrics['rr']}`
- Max Drawdown: `{metrics['max_drawdown']}`
- EV / trade: `{metrics['ev_per_trade']}`
- Sharpe: `{metrics['sharpe']}`

## Rule Check (initial)

- EV > 0: `{metrics['ev_per_trade'] > 0}`
- MaxDD <= 0.15: `{metrics['max_drawdown'] <= 0.15}`
- Trades >= 30: `{metrics['total_trades'] >= 30}`
"""
    report_path.write_text(report, encoding="utf-8")

    return {
        "params": params_path,
        "metrics": metrics_path,
        "trades": trades_path,
        "equity": equity_path,
        "report": report_path,
    }
