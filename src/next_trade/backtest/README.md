# NEXT-TRADE Backtest (PHASE-S1)

CLI 예시:

```powershell
python -m next_trade.backtest.cli --symbol BTCUSDT --tf 15m --days 60 --strategy s1_trend_pullback --fee_bps 4 --slippage_bps 1 --notional 100 --run_id BT_RUN_YYYYMMDD_HHMM
```

산출물:

- `evidence/phase-s1-bt/<run_id>/params.json`
- `evidence/phase-s1-bt/<run_id>/metrics.json`
- `evidence/phase-s1-bt/<run_id>/equity_curve.csv`
- `evidence/phase-s1-bt/<run_id>/trades.csv`
- `evidence/phase-s1-bt/<run_id>/report.md`
