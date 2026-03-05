from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List

ROOT = Path(r"C:\projects\NEXT-TRADE")
PERF_TRADES = ROOT / "evidence" / "evergreen" / "perf_trades.jsonl"
TABLE_FILE = ROOT / "evidence" / "analysis" / "shadow_strategy_table.json"
OUT_FILE = ROOT / "evidence" / "analysis" / "strategy_validation_report.json"


def _iter_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return []
    rows: List[dict] = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _bucket_of(row: dict) -> str:
    bb = str(row.get("bb_pos", "UNKNOWN")).upper()
    sq = str(row.get("bb_squeeze", "UNKNOWN")).upper()
    ha = str(row.get("ha_trend_dir", "UNKNOWN")).upper()
    return f"{ha}_{bb}_{sq}"


def _metrics(pnls: List[float]) -> Dict[str, float | int]:
    n = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss_abs = abs(sum(p for p in pnls if p < 0))
    winrate = wins / n if n else 0.0
    expectancy = sum(pnls) / n if n else 0.0
    pf = (gross_profit / gross_loss_abs) if gross_loss_abs > 0 else (999.0 if gross_profit > 0 else 0.0)
    return {
        "trades": n,
        "wins": wins,
        "losses": losses,
        "winrate": round(winrate, 6),
        "expectancy": round(expectancy, 8),
        "profit_factor": round(pf, 6),
        "pnl_sum": round(sum(pnls), 8),
    }


def validate(
    perf_trades: Path = PERF_TRADES,
    table_file: Path = TABLE_FILE,
    out_file: Path = OUT_FILE,
) -> Dict:
    table = json.loads(table_file.read_text(encoding="utf-8"))
    weights = {w["bucket"]: float(w.get("weight_proposed", 0.0)) for w in table.get("weights", [])}

    baseline_pnls: List[float] = []
    weighted_pnls: List[float] = []

    for row in _iter_jsonl(perf_trades):
        pnl = float(row.get("pnl_net", row.get("pnl", row.get("realized_pnl", 0.0))) or 0.0)
        baseline_pnls.append(pnl)
        bucket = _bucket_of(row)
        w = weights.get(bucket, 0.0)
        # Shadow-only replay metric: scaled contribution (no execution impact).
        weighted_pnls.append(pnl * (1.0 + w))

    baseline = _metrics(baseline_pnls)
    shadow = _metrics(weighted_pnls)

    out = {
        "source_perf_trades": str(perf_trades),
        "source_shadow_table": str(table_file),
        "baseline": baseline,
        "shadow_replay": shadow,
        "delta": {
            "expectancy": round(float(shadow["expectancy"]) - float(baseline["expectancy"]), 8),
            "profit_factor": round(float(shadow["profit_factor"]) - float(baseline["profit_factor"]), 6),
            "pnl_sum": round(float(shadow["pnl_sum"]) - float(baseline["pnl_sum"]), 8),
        },
        "status": "PASS" if float(shadow["expectancy"]) >= float(baseline["expectancy"]) else "WARN",
    }
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    report = validate()
    print(str(OUT_FILE))
    print(f"status={report['status']}")

