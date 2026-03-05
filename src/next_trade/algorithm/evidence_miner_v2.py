from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

ROOT = Path(r"C:\projects\NEXT-TRADE")
PERF_TRADES = ROOT / "evidence" / "evergreen" / "perf_trades.jsonl"
OUT_DIR = ROOT / "evidence" / "analysis"
OUT_FILE = OUT_DIR / "mined_patterns_v2.json"


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


def _to_float(v: object, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _trend_strength_bucket(row: dict) -> str:
    ts = _to_float(row.get("ha_trend_strength"), -1.0)
    if ts < 0:
        return "trend_strength_unknown"
    if ts < 25:
        return "trend_strength_low"
    if ts < 60:
        return "trend_strength_mid"
    return "trend_strength_high"


def _time_regime_bucket(row: dict) -> str:
    ts = str(row.get("ha_bb_bar_close_ts") or row.get("ts") or "")
    if not ts:
        return "time_regime_unknown"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        h = dt.hour
        if 0 <= h < 8:
            return "time_asia"
        if 8 <= h < 16:
            return "time_europe"
        return "time_us"
    except Exception:
        return "time_regime_unknown"


def _spread_bucket(row: dict) -> str:
    # Approx spread proxy from bb_width if direct spread unavailable.
    width = _to_float(row.get("bb_width"), -1.0)
    if width < 0:
        return "spread_unknown"
    if width < 0.002:
        return "spread_tight"
    if width < 0.006:
        return "spread_normal"
    return "spread_wide"


def _liquidity_bucket(row: dict) -> str:
    qty = abs(_to_float(row.get("qty"), 0.0))
    if qty <= 0:
        return "liquidity_unknown"
    if qty < 0.002:
        return "liquidity_low"
    if qty < 0.01:
        return "liquidity_mid"
    return "liquidity_high"


@dataclass
class Stat:
    key: str
    sample: int = 0
    wins: int = 0
    pnl_sum: float = 0.0

    def add(self, pnl: float) -> None:
        self.sample += 1
        self.pnl_sum += pnl
        if pnl > 0:
            self.wins += 1

    def as_dict(self) -> Dict[str, float | int | str]:
        win_rate = self.wins / self.sample if self.sample else 0.0
        expectancy = self.pnl_sum / self.sample if self.sample else 0.0
        return {
            "bucket": self.key,
            "sample": self.sample,
            "win_rate": round(win_rate, 6),
            "expectancy": round(expectancy, 8),
            "pnl_sum": round(self.pnl_sum, 8),
        }


def mine_patterns_v2(
    perf_trades: Path = PERF_TRADES, out_file: Path = OUT_FILE, min_sample: int = 5
) -> dict:
    axes: Dict[str, Dict[str, Stat]] = {
        "trend_strength": {},
        "time_regime": {},
        "spread": {},
        "liquidity": {},
    }
    total = 0
    for row in _iter_jsonl(perf_trades):
        pnl = _to_float(row.get("pnl_net", row.get("pnl", row.get("realized_pnl", 0.0))), 0.0)
        keys = {
            "trend_strength": _trend_strength_bucket(row),
            "time_regime": _time_regime_bucket(row),
            "spread": _spread_bucket(row),
            "liquidity": _liquidity_bucket(row),
        }
        for axis, key in keys.items():
            if key not in axes[axis]:
                axes[axis][key] = Stat(key=key)
            axes[axis][key].add(pnl)
        total += 1

    patterns: Dict[str, List[dict]] = {}
    for axis, bucket_map in axes.items():
        rows = [s.as_dict() for s in bucket_map.values() if s.sample >= min_sample]
        rows.sort(key=lambda x: (x["expectancy"], x["win_rate"], x["sample"]), reverse=True)
        patterns[axis] = rows

    payload = {
        "version": "v2",
        "stamp": datetime.now().isoformat(),
        "source": str(perf_trades),
        "total_trades": total,
        "min_sample": min_sample,
        "axes": patterns,
    }
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    out = mine_patterns_v2()
    print(str(OUT_FILE))
    print(f"total_trades={out['total_trades']}")

