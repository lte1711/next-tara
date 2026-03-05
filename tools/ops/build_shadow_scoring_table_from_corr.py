import argparse
import json
import re
from datetime import datetime
from pathlib import Path


def _to_float(v: str, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _to_int(v: str, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _parse_corr_file(path: Path) -> tuple[list[dict], int]:
    rows: list[dict] = []
    min_sample = 30
    if not path.exists():
        return rows, min_sample

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("sample_rule="):
            m = re.search(r"n>=(\d+)", s)
            if m:
                min_sample = _to_int(m.group(1), 30)
            continue
        if s.startswith("COLUMNS="):
            continue
        if "|" not in s:
            continue
        # Expected:
        # regime|ha_dir|bb_mode|bb_pos|n_trades|winrate|expectancy|profit_factor|max_dd|max_loss_streak|insufficient_sample
        parts = s.split("|")
        if len(parts) < 11:
            continue
        if parts[0].upper() in {"REGIME", "COLUMNS"}:
            continue
        rows.append(
            {
                "regime": parts[0].strip(),
                "ha_dir": parts[1].strip(),
                "bb_mode": parts[2].strip(),
                "bb_pos": parts[3].strip(),
                "n": _to_int(parts[4].strip(), 0),
                "winrate": _to_float(parts[5].strip(), 0.0),
                "expectancy": _to_float(parts[6].strip(), 0.0),
                "profit_factor": (
                    float("inf")
                    if parts[7].strip().upper() == "INF"
                    else _to_float(parts[7].strip(), 0.0)
                ),
                "max_dd": _to_float(parts[8].strip(), 0.0),
                "max_loss_streak": _to_int(parts[9].strip(), 0),
                "insufficient_sample": parts[10].strip().upper() == "YES",
            }
        )
    return rows, min_sample


def _score_row(r: dict, min_sample: int) -> float:
    # Conservative shadow score: positive expectancy/pf rewarded, drawdown/streak penalized.
    if r["n"] < min_sample:
        return 0.0
    if r["expectancy"] <= 0:
        return 0.0
    pf = 3.0 if r["profit_factor"] == float("inf") else max(0.0, r["profit_factor"])
    dd_penalty = 1.0 / (1.0 + max(0.0, r["max_dd"]))
    streak_penalty = 1.0 / (1.0 + max(0, r["max_loss_streak"]))
    return max(0.0, r["expectancy"]) * (0.5 + min(pf, 3.0) / 3.0) * dd_penalty * streak_penalty


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corr", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--topk", type=int, default=15)
    args = ap.parse_args()

    corr_path = Path(args.corr)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows, min_sample = _parse_corr_file(corr_path)
    scored = []
    for r in rows:
        r2 = dict(r)
        r2["score"] = _score_row(r2, min_sample)
        scored.append(r2)
    scored.sort(key=lambda x: x["score"], reverse=True)
    selected = scored[: max(1, int(args.topk))]

    # Conservative weighting: individual <= 0.15, total <= 1.0
    total_score = sum(x["score"] for x in selected)
    rules = []
    weight_sum = 0.0
    for x in selected:
        raw_w = (x["score"] / total_score) if total_score > 0 else 0.0
        w = min(0.15, raw_w)
        rules.append(
            {
                "regime": x["regime"],
                "signal": f"HA_{x['ha_dir']}|BB_{x['bb_mode']}|POS_{x['bb_pos']}",
                "n": x["n"],
                "corr": round(x["score"], 8),
                "weight_proposed": round(w, 6),
                "note": "shadow-only (no engine apply)",
                "metrics": {
                    "winrate": round(x["winrate"], 6),
                    "expectancy": round(x["expectancy"], 8),
                    "profit_factor": ("INF" if x["profit_factor"] == float("inf") else round(x["profit_factor"], 6)),
                    "max_dd": round(x["max_dd"], 8),
                    "max_loss_streak": int(x["max_loss_streak"]),
                    "insufficient_sample": bool(x["insufficient_sample"]),
                    "sample_rule": f"n>={min_sample}",
                },
            }
        )
        weight_sum += w

    # If we exceeded 1.0 via caps, renormalize down conservatively.
    if weight_sum > 1.0 and weight_sum > 0:
        scale = 1.0 / weight_sum
        for r in rules:
            r["weight_proposed"] = round(r["weight_proposed"] * scale, 6)

    payload = {
        "stamp": datetime.now().strftime("PH7C_SHADOW_%Y%m%d_%H%M%S"),
        "source_corr_file": str(corr_path),
        "topk": int(args.topk),
        "sample_rule": f"n>={min_sample}",
        "rules": rules,
        "notes": [
            "shadow-only table; no engine/order logic changes",
            "conservative caps: per-rule <= 0.15, sum <= 1.0",
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
