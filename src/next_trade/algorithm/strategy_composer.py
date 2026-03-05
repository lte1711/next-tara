from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

ROOT = Path(r"C:\projects\NEXT-TRADE")
IN_FILE = ROOT / "evidence" / "analysis" / "mined_patterns.json"
OUT_FILE = ROOT / "evidence" / "analysis" / "shadow_strategy_table.json"


def _propose_weight(expectancy: float, win_rate: float, sample: int) -> float:
    # Conservative scoring: positive expectancy only, saturating with sample.
    if expectancy <= 0:
        return 0.0
    sample_factor = min(1.0, sample / 80.0)
    quality = max(0.0, min(1.0, (win_rate - 0.45) / 0.25))
    raw = 0.12 * sample_factor * quality
    return max(0.0, min(0.12, raw))


def compose_strategy(
    in_file: Path = IN_FILE,
    out_file: Path = OUT_FILE,
    max_weight_sum: float = 0.50,
) -> Dict:
    payload = json.loads(in_file.read_text(encoding="utf-8"))
    patterns: List[Dict] = payload.get("patterns", [])

    entries: List[Dict] = []
    for p in patterns:
        w = _propose_weight(
            float(p.get("expectancy", 0.0)),
            float(p.get("win_rate", 0.0)),
            int(p.get("sample", 0)),
        )
        entries.append(
            {
                "bucket": p.get("bucket", "unknown"),
                "sample": int(p.get("sample", 0)),
                "win_rate": float(p.get("win_rate", 0.0)),
                "expectancy": float(p.get("expectancy", 0.0)),
                "weight_proposed": w,
            }
        )

    entries.sort(key=lambda x: x["weight_proposed"], reverse=True)

    # Enforce WEIGHT_SUM <= 0.50
    total = 0.0
    for e in entries:
        allowed = max(0.0, max_weight_sum - total)
        if allowed <= 0:
            e["weight_proposed"] = 0.0
            continue
        e["weight_proposed"] = round(min(e["weight_proposed"], allowed), 6)
        total += e["weight_proposed"]

    out = {
        "source": str(in_file),
        "constraints": {"weight_sum_max": max_weight_sum, "weight_max_each": 0.12},
        "weights": entries,
        "weight_sum": round(sum(float(x["weight_proposed"]) for x in entries), 6),
    }
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    result = compose_strategy()
    print(str(OUT_FILE))
    print(f"weights={len(result['weights'])} weight_sum={result['weight_sum']}")

