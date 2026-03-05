from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .data_binance import load_or_download_klines
from .engine import BacktestConfig, run_backtest
from .report import write_outputs
from .strategies.s1_trend_pullback import S1TrendPullbackStrategy
from .strategies.s2_atr_breakout import S2AtrBreakoutStrategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NEXT-TRADE PHASE-S1 Backtest CLI")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--tf", default="15m")
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--strategy", default="s1_trend_pullback")
    parser.add_argument("--fee_bps", type=float, default=4.0)
    parser.add_argument("--slippage_bps", type=float, default=1.0)
    parser.add_argument("--notional", type=float, default=100.0)
    parser.add_argument("--k", type=float, default=2.0, help="ATR channel multiplier for S2")
    parser.add_argument("--m", type=float, default=1.5, help="SL ATR multiplier for S2")
    parser.add_argument("--n", type=float, default=3.0, help="TP ATR multiplier for S2")
    parser.add_argument("--ha_filter", action="store_true", help="Enable Heikin-Ashi entry filter for S2")
    parser.add_argument("--ha_confirm_n", type=int, default=2, help="HA confirmation bars (default: 2)")
    parser.add_argument("--ha_lookback", type=int, default=60, help="HA lookback bars (default: 60)")
    parser.add_argument("--start", type=str, default=None, help="ISO8601 UTC start (e.g. 2025-02-24T00:00:00Z)")
    parser.add_argument("--end", type=str, default=None, help="ISO8601 UTC end (e.g. 2026-02-24T00:00:00Z)")
    parser.add_argument("--run_id", default=None)
    parser.add_argument("--force_refresh", action="store_true")
    return parser.parse_args()


def parse_iso8601_to_ms(raw: str) -> int:
    normalized = raw.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[3]

    if args.symbol != "BTCUSDT":
        raise ValueError("BT-001 scope is fixed to BTCUSDT")
    allowed_tf = {"15m", "1h", "4h"}
    if args.tf not in allowed_tf:
        raise ValueError(f"Unsupported timeframe: {args.tf}. Allowed: {sorted(allowed_tf)}")

    run_id = args.run_id or f"BT_RUN_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M')}"
    out_dir = project_root / "evidence" / "phase-s1-bt" / run_id

    if args.strategy == "s1_trend_pullback":
        strategy = S1TrendPullbackStrategy()
    elif args.strategy == "s2_atr_breakout":
        strategy = S2AtrBreakoutStrategy(
            k=args.k,
            m=args.m,
            n=args.n,
            ha_filter_enabled=args.ha_filter,
            ha_confirm_n=args.ha_confirm_n,
            ha_lookback=args.ha_lookback,
        )
    else:
        raise ValueError(f"Unsupported strategy: {args.strategy}")

    range_mode = False
    start_ms: int | None = None
    end_ms: int | None = None
    if args.start or args.end:
        if not (args.start and args.end):
            raise ValueError("Both --start and --end must be provided together")
        start_ms = parse_iso8601_to_ms(args.start)
        end_ms = parse_iso8601_to_ms(args.end)
        if start_ms >= end_ms:
            raise ValueError("--start must be < --end")
        range_mode = True
        print("[BT-004] range mode enabled: --start/--end takes precedence over --days")

    candles = load_or_download_klines(
        project_root=project_root,
        symbol=args.symbol,
        interval=args.tf,
        days=args.days,
        start_ms=start_ms,
        end_ms=end_ms,
        force_refresh=args.force_refresh,
    )
    if not candles:
        raise RuntimeError("No candles downloaded/loaded")

    if range_mode:
        candles = [c for c in candles if int(c["open_time"]) >= int(start_ms) and int(c["open_time"]) < int(end_ms)]
        if not candles:
            raise RuntimeError("No candles in selected range")

    cfg = BacktestConfig(
        symbol=args.symbol,
        timeframe=args.tf,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        notional=args.notional,
    )

    metrics, trades, equity_curve = run_backtest(candles, strategy, cfg)

    params = {
        "mode": "range" if range_mode else "days",
        "symbol": args.symbol,
        "tf": args.tf,
        "days": args.days,
        "start": args.start,
        "end": args.end,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "strategy": args.strategy,
        "fee_bps": args.fee_bps,
        "slippage_bps": args.slippage_bps,
        "notional": args.notional,
        "k": args.k,
        "m": args.m,
        "n": args.n,
        "ha_filter": args.ha_filter,
        "ha_confirm_n": args.ha_confirm_n,
        "ha_lookback": args.ha_lookback,
        "run_id": run_id,
        "force_refresh": args.force_refresh,
    }

    paths = write_outputs(out_dir, params, metrics, trades, equity_curve)

    print("[BT-001] Completed")
    print(f"[BT-001] out_dir={out_dir}")
    print("[BT-001] metrics=")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    for key, path in paths.items():
        print(f"[BT-001] {key}: {path}")


if __name__ == "__main__":
    main()
