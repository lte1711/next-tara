import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


PERF_TRADES_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf_trades.jsonl"
EVENTS_DEFAULT = r"C:\projects\NEXT-TRADE\logs\runtime\profitmax_v1_events.jsonl"
OUT_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf"


def _to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _normalize_regime(v: str) -> str:
    x = (v or "").strip().lower()
    if x in {"range", "ranging"}:
        return "RANGE"
    if x in {"trend", "trending"}:
        return "TREND"
    if x in {"high_vol", "shock", "spike"}:
        return "SHOCK"
    return ""


def _infer_regime_from_trade(rec: dict) -> tuple[str, str]:
    hint = _normalize_regime(str(rec.get("regime_hint") or ""))
    if hint:
        return hint, "regime_hint"

    ep = _to_float(rec.get("price_entry"), 0.0)
    xp = _to_float(rec.get("price_exit"), 0.0)
    pnl = _to_float(rec.get("pnl_net", rec.get("realized_pnl", 0.0)), 0.0)
    qty = abs(_to_float(rec.get("qty"), 0.0))
    notion = ep * qty if ep > 0 and qty > 0 else 0.0
    move_ratio = abs(xp - ep) / ep if ep > 0 else 0.0
    pnl_ratio = abs(pnl) / notion if notion > 0 else 0.0

    # Conservative fallback rules (documented deterministic behavior).
    if move_ratio >= 0.004 or pnl_ratio >= 0.003:
        return "SHOCK", "fallback_ratio"
    if move_ratio >= 0.0015:
        return "TREND", "fallback_ratio"
    return "RANGE", "fallback_ratio"


def _load_trace_regime(events_path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not events_path.exists():
        return out
    with events_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            et = str(ev.get("event_type") or "").upper()
            if et != "ENTRY":
                continue
            payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
            trace_id = str(payload.get("trace_id") or "").strip()
            if not trace_id:
                continue
            rg = _normalize_regime(str(payload.get("regime") or ""))
            if rg:
                out[trace_id] = rg
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perf_trades", default=PERF_TRADES_DEFAULT)
    ap.add_argument("--events", default=EVENTS_DEFAULT)
    ap.add_argument("--out_dir", default=OUT_DIR_DEFAULT)
    args = ap.parse_args()

    perf_path = Path(args.perf_trades)
    events_path = Path(args.events)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    trace_regime = _load_trace_regime(events_path)
    rows = []
    count_by_regime = Counter()
    count_by_source = Counter()
    unknown = 0

    if perf_path.exists():
        with perf_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                trade_id = str(rec.get("trade_id") or "")
                trace_id = str(rec.get("trace_id") or "")
                ts = str(rec.get("ts") or "")

                regime = ""
                source = ""
                if trace_id and trace_id in trace_regime:
                    regime = trace_regime[trace_id]
                    source = "entry_trace"
                if not regime:
                    regime, source = _infer_regime_from_trade(rec)
                if regime not in {"RANGE", "TREND", "SHOCK"}:
                    regime = "UNKNOWN"
                    source = "unknown"
                    unknown += 1

                count_by_regime[regime] += 1
                count_by_source[source] += 1
                rows.append(
                    {
                        "trade_id": trade_id,
                        "trace_id": trace_id,
                        "ts": ts,
                        "signal_id": str(rec.get("signal_id") or "mean_reversion"),
                        "strategy_mode": str(rec.get("strategy_mode") or "MR_ONLY"),
                        "regime_tag": regime,
                        "regime_source": source,
                    }
                )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    map_path = out_dir / f"regime_map_{stamp}.jsonl"
    rpt_path = out_dir / f"regime_report_{stamp}.txt"

    with map_path.open("w", encoding="utf-8") as w:
        for row in rows:
            w.write(json.dumps(row, ensure_ascii=False) + "\n")

    lines = [
        f"STAMP=REGIME_{stamp}",
        f"PERF_TRADES={perf_path}",
        f"EVENTS={events_path}",
        f"TRADES_TOTAL={len(rows)}",
        f"RANGE={count_by_regime.get('RANGE',0)} TREND={count_by_regime.get('TREND',0)} SHOCK={count_by_regime.get('SHOCK',0)} UNKNOWN={count_by_regime.get('UNKNOWN',0)}",
        f"MAP_SOURCE_COUNTS={json.dumps(dict(count_by_source), ensure_ascii=False)}",
        f"REGIME_MAP_FILE={map_path}",
        f"STATUS={'OK' if unknown == 0 else 'WARN'}",
        "NOTE=Unknown tags use deterministic fallback and are explicitly counted.",
    ]
    rpt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(str(map_path))
    print(str(rpt_path))


if __name__ == "__main__":
    main()

