import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


DEFAULT_TRADES = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf_trades.jsonl"


def _to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def _load_trades(path: Path):
    rows = []
    if not path.exists():
        return rows
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


def _regime(t: dict):
    rg = str(t.get("regime_tag") or t.get("regime_hint") or "UNKNOWN").upper()
    return rg if rg else "UNKNOWN"


def _ha_state(t: dict):
    return str(t.get("ha_trend_dir") or "UNKNOWN").upper()


def _bb_state(t: dict):
    sq = str(t.get("bb_squeeze") or "UNKNOWN").upper()
    pos = str(t.get("bb_pos") or "UNKNOWN").upper()
    if sq == "YES":
        return "BB_SQUEEZE"
    if pos in {"ABOVE_UPPER", "BELOW_LOWER"}:
        return "BB_BOUNCE"
    if pos in {"ABOVE_MID", "BELOW_MID", "AROUND_MID", "INSIDE"}:
        return "BB_TREND_RIDE"
    return "BB_UNKNOWN"


def _match_rule(trade: dict, rules: list[dict]):
    rg = _regime(trade)
    ha = _ha_state(trade)
    bb = _bb_state(trade)

    # Priority: L1 -> L2 -> L0
    for r in rules:
        if str(r.get("level")) == "L1":
            if r.get("regime") == rg and str(r.get("signal")) == f"HA_{ha}":
                return r
    for r in rules:
        if str(r.get("level")) == "L2":
            if r.get("regime") == rg and str(r.get("signal")) == bb:
                return r
    for r in rules:
        if str(r.get("level")) == "L0":
            if r.get("regime") == rg:
                return r
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True)
    ap.add_argument("--trades", default=DEFAULT_TRADES)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    table = _load_json(Path(args.table))
    rules = table.get("rules", [])
    trades = _load_trades(Path(args.trades))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    total = len(trades)
    low = 0
    high = 0
    matched = 0
    bucket = Counter()
    pnl_low = 0.0
    pnl_high = 0.0
    threshold_low = 0.02
    threshold_high = 0.07

    for t in trades:
        pnl = _to_float(t.get("pnl_net", t.get("realized_pnl", 0.0)), 0.0)
        r = _match_rule(t, rules)
        score = _to_float((r or {}).get("weight_proposed"), 0.0)
        if r:
            matched += 1
            bucket[f"{r.get('level')}:{r.get('regime')}:{r.get('signal')}"] += 1
        else:
            bucket["UNMATCHED"] += 1
        if score <= threshold_low:
            low += 1
            pnl_low += pnl
        if score >= threshold_high:
            high += 1
            pnl_high += pnl

    lines = [
        f"STAMP=PH7C_SHADOW_REPLAY_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        f"SOURCE_TABLE={args.table}",
        f"SOURCE_TRADES={args.trades}",
        f"TOTAL_TRADES={total}",
        f"MATCHED_RULES={matched}",
        f"LOW_SCORE_THRESHOLD={threshold_low}",
        f"HIGH_SCORE_THRESHOLD={threshold_high}",
        f"LOW_SCORE_TRADES={low}",
        f"HIGH_SCORE_TRADES={high}",
        f"LOW_SCORE_PNL_SUM={pnl_low:.8f}",
        f"HIGH_SCORE_PNL_SUM={pnl_high:.8f}",
        f"TOP_BUCKETS={json.dumps(bucket.most_common(10), ensure_ascii=False)}",
        "NOTE=shadow replay only; no execution path impact",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()

