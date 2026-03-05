from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

ROOT = Path(r"C:\projects\NEXT-TRADE")
PERF_TRADES = ROOT / "evidence" / "evergreen" / "perf_trades.jsonl"
OUT_DIR = ROOT / "evidence" / "analysis"
OUT_FILE = OUT_DIR / "mined_patterns.json"


@dataclass
class BucketStats:
    bucket: str
    sample: int = 0
    wins: int = 0
    losses: int = 0
    pnl_sum: float = 0.0

    def add(self, pnl: float) -> None:
        self.sample += 1
        self.pnl_sum += pnl
        if pnl > 0:
            self.wins += 1
        elif pnl < 0:
            self.losses += 1

    def to_dict(self) -> Dict[str, float | int | str]:
        win_rate = (self.wins / self.sample) if self.sample else 0.0
        expectancy = (self.pnl_sum / self.sample) if self.sample else 0.0
        return {
            "bucket": self.bucket,
            "win_rate": round(win_rate, 6),
            "sample": self.sample,
            "expectancy": round(expectancy, 8),
            "pnl_sum": round(self.pnl_sum, 8),
            "wins": self.wins,
            "losses": self.losses,
        }


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
    # Conservative, deterministic bucketization from existing perf_trades fields.
    bb = str(row.get("bb_pos", "UNKNOWN")).upper()
    sq = str(row.get("bb_squeeze", "UNKNOWN")).upper()
    ha = str(row.get("ha_trend_dir", "UNKNOWN")).upper()
    return f"{ha}_{bb}_{sq}"


def mine_patterns(
    perf_trades: Path = PERF_TRADES,
    out_file: Path = OUT_FILE,
    min_sample: int = 5,
) -> dict:
    buckets: Dict[str, BucketStats] = {}
    total = 0
    for row in _iter_jsonl(perf_trades):
        pnl = float(row.get("pnl_net", row.get("pnl", row.get("realized_pnl", 0.0))) or 0.0)
        key = _bucket_of(row)
        if key not in buckets:
            buckets[key] = BucketStats(bucket=key)
        buckets[key].add(pnl)
        total += 1

    patterns = [b.to_dict() for b in buckets.values() if b.sample >= min_sample]
    patterns.sort(key=lambda x: (x["expectancy"], x["win_rate"], x["sample"]), reverse=True)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": str(perf_trades),
        "total_trades": total,
        "min_sample": min_sample,
        "patterns": patterns,
    }
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    data = mine_patterns()
    print(str(OUT_FILE))
    print(f"patterns={len(data['patterns'])} total_trades={data['total_trades']}")

