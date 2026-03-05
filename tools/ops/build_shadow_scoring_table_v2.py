import argparse
import json
from collections import defaultdict
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


def _parse_corr(path: Path):
    rows = []
    min_n = 30
    if not path.exists():
        return rows, min_n

    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("sample_rule="):
            # expected sample_rule=n>=30
            p = s.split(">=")
            if len(p) == 2:
                min_n = _to_int(p[1], 30)
            continue
        if s.startswith("COLUMNS=") or s.startswith("---") or s.startswith("STAMP=") or s.startswith("SOURCE=") or s.startswith("TOTAL_TRADES="):
            continue
        if "|" not in s:
            continue
        parts = s.split("|")
        if len(parts) < 11:
            continue
        pf_txt = parts[7].strip()
        pf_val = float("inf") if pf_txt.upper() == "INF" else _to_float(pf_txt, 0.0)
        rows.append(
            {
                "regime": parts[0].strip(),
                "ha_dir": parts[1].strip(),
                "bb_mode": parts[2].strip(),
                "bb_pos": parts[3].strip(),
                "n": _to_int(parts[4].strip(), 0),
                "winrate": _to_float(parts[5].strip(), 0.0),
                "expectancy": _to_float(parts[6].strip(), 0.0),
                "profit_factor": pf_val,
                "max_dd": _to_float(parts[8].strip(), 0.0),
                "max_loss_streak": _to_int(parts[9].strip(), 0),
                "insufficient_sample": parts[10].strip().upper() == "YES",
            }
        )
    return rows, min_n


def _rollup_weighted(rows):
    n_sum = sum(r["n"] for r in rows)
    if n_sum <= 0:
        return None
    w = lambda k: sum(r[k] * r["n"] for r in rows) / n_sum
    return {
        "n": n_sum,
        "winrate": w("winrate"),
        "expectancy": w("expectancy"),
        "max_dd": w("max_dd"),
        "max_loss_streak": w("max_loss_streak"),
        "profit_factor": w("profit_factor")
        if all(r["profit_factor"] != float("inf") for r in rows)
        else float("inf"),
    }


def _score(metric, min_n):
    if metric["n"] < min_n:
        return 0.0
    if metric["expectancy"] <= 0:
        return 0.0
    pf = 3.0 if metric["profit_factor"] == float("inf") else max(0.0, min(metric["profit_factor"], 3.0))
    dd_pen = 1.0 / (1.0 + max(metric["max_dd"], 0.0))
    streak_pen = 1.0 / (1.0 + max(metric["max_loss_streak"], 0.0))
    return metric["expectancy"] * (0.5 + pf / 3.0) * dd_pen * streak_pen


def _build_candidates(rows, min_n):
    levels = defaultdict(list)
    # L0: regime
    g0 = defaultdict(list)
    # L1: regime x HA
    g1 = defaultdict(list)
    # L2: regime x BB_MODE
    g2 = defaultdict(list)
    # L3: regime x HA x BB_MODE x BB_POS (reference only)
    g3 = defaultdict(list)

    for r in rows:
        g0[(r["regime"],)].append(r)
        g1[(r["regime"], r["ha_dir"])].append(r)
        g2[(r["regime"], r["bb_mode"])].append(r)
        g3[(r["regime"], r["ha_dir"], r["bb_mode"], r["bb_pos"])].append(r)

    for key, grp in g0.items():
        m = _rollup_weighted(grp)
        if not m:
            continue
        levels["L0"].append({"key": key, "metric": m, "score": _score(m, min_n)})
    for key, grp in g1.items():
        m = _rollup_weighted(grp)
        if not m:
            continue
        levels["L1"].append({"key": key, "metric": m, "score": _score(m, min_n)})
    for key, grp in g2.items():
        m = _rollup_weighted(grp)
        if not m:
            continue
        levels["L2"].append({"key": key, "metric": m, "score": _score(m, min_n)})
    for key, grp in g3.items():
        m = _rollup_weighted(grp)
        if not m:
            continue
        levels["L3"].append({"key": key, "metric": m, "score": 0.0})  # Always reference-only

    return levels


def _rule_obj(level, key, metric, score):
    if level == "L0":
        regime = key[0]
        signal = "LEVEL0_REGIME"
    elif level == "L1":
        regime = key[0]
        signal = f"HA_{key[1]}"
    elif level == "L2":
        regime = key[0]
        signal = f"BB_{key[1]}"
    else:
        regime = key[0]
        signal = f"HA_{key[1]}|BB_{key[2]}|POS_{key[3]}"
    pf = metric["profit_factor"]
    return {
        "level": level,
        "regime": regime,
        "signal": signal,
        "n": int(metric["n"]),
        "corr": round(score, 8),
        "weight_proposed": 0.0,  # filled later
        "note": "shadow-only (no engine apply)",
        "metrics": {
            "winrate": round(metric["winrate"], 6),
            "expectancy": round(metric["expectancy"], 8),
            "profit_factor": "INF" if pf == float("inf") else round(pf, 6),
            "max_dd": round(metric["max_dd"], 8),
            "max_loss_streak": round(metric["max_loss_streak"], 4),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corr", required=True)
    ap.add_argument("--out_json", required=True)
    ap.add_argument("--out_txt", required=True)
    ap.add_argument("--topk", type=int, default=15)
    ap.add_argument("--min_n", type=int, default=30)
    ap.add_argument("--max_weight", type=float, default=0.10)
    ap.add_argument("--max_weight_sum", type=float, default=0.50)
    args = ap.parse_args()

    corr_path = Path(args.corr)
    out_json = Path(args.out_json)
    out_txt = Path(args.out_txt)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_txt.parent.mkdir(parents=True, exist_ok=True)

    rows, file_min_n = _parse_corr(corr_path)
    min_n = max(args.min_n, file_min_n)
    levels = _build_candidates(rows, min_n)

    # choose candidates from L1/L2/L0 in this priority. L3 is reference only.
    chosen = []
    for lv in ("L1", "L2", "L0"):
        for c in levels.get(lv, []):
            chosen.append((lv, c))
    chosen.sort(key=lambda x: x[1]["score"], reverse=True)
    chosen = chosen[: max(1, int(args.topk))]

    rules = []
    positive = [c for c in chosen if c[1]["score"] > 0]
    score_sum = sum(c[1]["score"] for c in positive)
    weight_sum = 0.0

    for lv, c in chosen:
        r = _rule_obj(lv, c["key"], c["metric"], c["score"])
        if c["score"] > 0 and c["metric"]["n"] >= min_n and score_sum > 0:
            w = min(args.max_weight, c["score"] / score_sum)
            r["weight_proposed"] = round(w, 6)
            weight_sum += r["weight_proposed"]
        else:
            r["weight_proposed"] = 0.0
        r["sample_rule"] = f"n>={min_n}"
        r["insufficient_sample"] = r["n"] < min_n
        rules.append(r)

    if weight_sum > args.max_weight_sum and weight_sum > 0:
        scale = args.max_weight_sum / weight_sum
        for r in rules:
            r["weight_proposed"] = round(r["weight_proposed"] * scale, 6)
        weight_sum = sum(r["weight_proposed"] for r in rules)

    payload = {
        "stamp": datetime.now().strftime("PH7C_SHADOW_V2_%Y%m%d_%H%M%S"),
        "source_corr_file": str(corr_path),
        "sample_rule": f"n>={min_n}",
        "caps": {
            "max_weight": args.max_weight,
            "max_weight_sum": args.max_weight_sum,
        },
        "level_coverage": {
            "L0": len(levels.get("L0", [])),
            "L1": len(levels.get("L1", [])),
            "L2": len(levels.get("L2", [])),
            "L3": len(levels.get("L3", [])),
        },
        "rules": rules,
        "notes": [
            "shadow-only; no engine apply",
            "L3 is reference-only and always weight=0",
            "coarse fallback priority: L1 -> L2 -> L0",
        ],
    }
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    nonzero = sum(1 for r in rules if r["weight_proposed"] > 0)
    max_w = max((r["weight_proposed"] for r in rules), default=0.0)
    lines = [
        f"STAMP={payload['stamp']}",
        f"SOURCE_CORR={corr_path}",
        f"sample_rule={payload['sample_rule']}",
        f"RULES_TOTAL={len(rules)}",
        f"RULES_WITH_NONZERO_WEIGHT={nonzero}",
        f"MAX_WEIGHT={max_w:.6f}",
        f"WEIGHT_SUM={weight_sum:.6f}",
        f"LEVEL_COVERAGE=L0:{payload['level_coverage']['L0']},L1:{payload['level_coverage']['L1']},L2:{payload['level_coverage']['L2']},L3:{payload['level_coverage']['L3']}",
    ]
    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out_json))
    print(str(out_txt))


if __name__ == "__main__":
    main()

