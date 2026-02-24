from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any

from .strategy_base import BaseStrategy


@dataclass
class BacktestConfig:
    symbol: str
    timeframe: str
    fee_bps: float
    slippage_bps: float
    notional: float
    sl_pct: float = 0.0015
    tp_pct: float = 0.0030
    starting_equity: float = 10_000.0


def _max_drawdown(equity_curve: list[dict[str, Any]]) -> float:
    peak = float("-inf")
    max_dd = 0.0
    for p in equity_curve:
        eq = float(p["equity"])
        peak = max(peak, eq)
        if peak > 0:
            dd = (peak - eq) / peak
            max_dd = max(max_dd, dd)
    return max_dd


def run_backtest(
    candles: list[dict[str, Any]],
    strategy: BaseStrategy,
    cfg: BacktestConfig,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    indicators = strategy.prepare(candles)

    fee_rate = cfg.fee_bps / 10_000.0
    slippage = cfg.slippage_bps / 10_000.0

    trades: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []
    equity = cfg.starting_equity

    position: dict[str, Any] | None = None

    for i in range(1, len(candles)):
        bar = candles[i]
        bar_open = float(bar["open"])
        bar_high = float(bar["high"])
        bar_low = float(bar["low"])
        bar_close = float(bar["close"])

        if position is None:
            sig = strategy.signal(i - 1, candles, indicators)
            if sig in ("long", "short"):
                if sig == "long":
                    entry = bar_open * (1.0 + slippage)
                else:
                    entry = bar_open * (1.0 - slippage)

                sl, tp = strategy.risk_levels(
                    index=i - 1,
                    side=sig,
                    entry_price=entry,
                    candles=candles,
                    indicators=indicators,
                    default_sl_pct=cfg.sl_pct,
                    default_tp_pct=cfg.tp_pct,
                )

                qty = cfg.notional / entry
                position = {
                    "side": sig,
                    "entry_price": entry,
                    "entry_time": int(bar["open_time"]),
                    "qty": qty,
                    "sl": sl,
                    "tp": tp,
                }

        if position is not None:
            side = position["side"]
            entry = float(position["entry_price"])
            qty = float(position["qty"])
            sl = float(position["sl"])
            tp = float(position["tp"])

            exit_price: float | None = None
            exit_reason: str | None = None

            if side == "long":
                sl_hit = bar_low <= sl
                tp_hit = bar_high >= tp
                if sl_hit and tp_hit:
                    exit_price = sl
                    exit_reason = "SL_AND_TP_SAME_BAR_USE_SL"
                elif sl_hit:
                    exit_price = sl
                    exit_reason = "SL"
                elif tp_hit:
                    exit_price = tp
                    exit_reason = "TP"
            else:
                sl_hit = bar_high >= sl
                tp_hit = bar_low <= tp
                if sl_hit and tp_hit:
                    exit_price = sl
                    exit_reason = "SL_AND_TP_SAME_BAR_USE_SL"
                elif sl_hit:
                    exit_price = sl
                    exit_reason = "SL"
                elif tp_hit:
                    exit_price = tp
                    exit_reason = "TP"

            if (exit_price is None) and (i == len(candles) - 1):
                exit_price = bar_close
                exit_reason = "EOD"

            if exit_price is not None and exit_reason is not None:
                if side == "long":
                    exit_eff = exit_price * (1.0 - slippage)
                    gross_pnl = (exit_eff - entry) * qty
                else:
                    exit_eff = exit_price * (1.0 + slippage)
                    gross_pnl = (entry - exit_eff) * qty

                fee_paid = ((entry * qty) + (exit_eff * qty)) * fee_rate
                net_pnl = gross_pnl - fee_paid
                equity += net_pnl

                trades.append(
                    {
                        "entry_time": position["entry_time"],
                        "exit_time": int(bar["close_time"]),
                        "side": side,
                        "entry_price": round(entry, 8),
                        "exit_price": round(exit_eff, 8),
                        "qty": round(qty, 8),
                        "gross_pnl": round(gross_pnl, 8),
                        "fee": round(fee_paid, 8),
                        "net_pnl": round(net_pnl, 8),
                        "reason": exit_reason,
                    }
                )
                position = None

        equity_curve.append({"time": int(bar["close_time"]), "equity": round(equity, 8)})

    total = len(trades)
    wins = [t for t in trades if float(t["net_pnl"]) > 0]
    losses = [t for t in trades if float(t["net_pnl"]) <= 0]

    gross_pnl_total = sum(float(t["gross_pnl"]) for t in trades)
    net_pnl_total = sum(float(t["net_pnl"]) for t in trades)
    avg_win = mean([float(t["net_pnl"]) for t in wins]) if wins else 0.0
    avg_loss = mean([abs(float(t["net_pnl"])) for t in losses]) if losses else 0.0
    rr = (avg_win / avg_loss) if avg_loss > 0 else 0.0
    ev_trade = (net_pnl_total / total) if total > 0 else 0.0

    returns = [float(t["net_pnl"]) / cfg.notional for t in trades] if trades else []
    sharpe = 0.0
    if len(returns) > 1:
        std = pstdev(returns)
        if std > 0:
            sharpe = (mean(returns) / std) * (252 ** 0.5)

    metrics = {
        "symbol": cfg.symbol,
        "timeframe": cfg.timeframe,
        "total_trades": total,
        "win_rate": (len(wins) / total) if total else 0.0,
        "gross_pnl": round(gross_pnl_total, 8),
        "net_pnl": round(net_pnl_total, 8),
        "avg_win": round(avg_win, 8),
        "avg_loss": round(avg_loss, 8),
        "rr": round(rr, 8),
        "max_drawdown": round(_max_drawdown(equity_curve), 8),
        "ev_per_trade": round(ev_trade, 8),
        "sharpe": round(sharpe, 8),
        "fee_bps": cfg.fee_bps,
        "slippage_bps": cfg.slippage_bps,
        "notional": cfg.notional,
    }
    return metrics, trades, equity_curve
