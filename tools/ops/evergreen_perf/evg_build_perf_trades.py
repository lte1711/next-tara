import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


EVENTS_DEFAULT = r"C:\projects\NEXT-TRADE\logs\runtime\profitmax_v1_events.jsonl"
OUT_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf_trades.jsonl"


def parse_side(payload: dict) -> str:
    side = str(payload.get("side") or "").upper()
    if side == "BUY":
        return "LONG"
    if side == "SELL":
        return "SHORT"
    return "UNKNOWN"


def normalize_ts(v) -> str:
    if isinstance(v, str) and v:
        return v
    return datetime.now(timezone.utc).isoformat()


def _last_closed_5m_ts(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        dt = datetime.now(timezone.utc)
    minute_floor = (dt.minute // 5) * 5
    snapped = dt.replace(minute=minute_floor, second=0, microsecond=0)
    return snapped.isoformat()


def build_record(event: dict) -> dict | None:
    et = str(event.get("event_type") or event.get("type") or "").upper()
    if et not in {"EXIT", "TP", "SL"}:
        return None

    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    realized = payload.get("realized_pnl", payload.get("pnl", 0.0))
    try:
        realized = float(realized)
    except Exception:
        realized = 0.0

    symbol = str(event.get("symbol") or payload.get("symbol") or "UNKNOWN")
    qty_raw = payload.get("qty", payload.get("quantity", 0.0))
    try:
        qty = float(qty_raw)
    except Exception:
        qty = 0.0

    entry_price = payload.get("entry_price", 0.0)
    exit_price = payload.get("exit_price", payload.get("price", 0.0))
    fee = payload.get("fee", payload.get("fee_total", 0.0))
    run_id = str(event.get("stamp") or payload.get("run_id") or "UNKNOWN")
    trace_id = str(payload.get("trace_id") or payload.get("entry_id") or "")
    strategy_id = str(payload.get("strategy_id") or "mean_reversion")
    signal_score = payload.get("signal_score")
    expected_edge = payload.get("expected_edge")
    regime = str(payload.get("regime") or payload.get("price_context") or "")
    ts_entry = payload.get("entry_ts") or payload.get("ts_entry")
    ts_exit = event.get("ts")

    try:
        entry_price = float(entry_price)
    except Exception:
        entry_price = 0.0
    try:
        exit_price = float(exit_price)
    except Exception:
        exit_price = 0.0
    try:
        fee = float(fee)
    except Exception:
        fee = 0.0

    try:
        signal_score = float(signal_score) if signal_score is not None else None
    except Exception:
        signal_score = None
    try:
        expected_edge = float(expected_edge) if expected_edge is not None else None
    except Exception:
        expected_edge = None

    ts_norm = normalize_ts(event.get("ts"))
    pnl_gross = realized + fee
    pnl_net = realized
    trade_id = trace_id or f"{symbol}-{ts_norm}"

    return {
        "trade_id": trade_id,
        "ts": ts_norm,
        "ts_entry": ts_entry,
        "ts_exit": normalize_ts(ts_exit),
        "symbol": symbol,
        "side": parse_side(payload),
        "qty": qty,
        "price_entry": entry_price,
        "price_exit": exit_price,
        "entry_price": entry_price,  # backward compatibility
        "exit_price": exit_price,    # backward compatibility
        "realized_pnl": realized,
        "pnl": realized,
        "pnl_gross": pnl_gross,
        "pnl_net": pnl_net,
        "fee": fee,
        "exit_reason": et,
        "run_id": run_id,
        "trace_id": trace_id,
        "strategy_id": strategy_id,
        "signal_id": "mean_reversion",
        "strategy_mode": "MR_ONLY",
        "entry_reason": "mr_signal",
        "mr_variant": "baseline",
        "regime_hint": regime,
        "signal_score": signal_score,
        "expected_edge": expected_edge,
        # Phase 7A: signal-only metadata (no execution impact).
        "tf": "5m",
        "ha_trend_dir": "UNKNOWN",
        "ha_trend_strength": None,
        "bb_pos": "UNKNOWN",
        "bb_width": None,
        "bb_squeeze": "UNKNOWN",
        "ha_bb_reason": "no_ohlc_source",
        "ha_bb_bar_close_ts": _last_closed_5m_ts(ts_norm),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=EVENTS_DEFAULT)
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args()

    events_path = Path(args.events)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not events_path.exists():
        out_path.write_text("", encoding="utf-8")
        print(str(out_path))
        print("COUNT=0")
        return

    records = []
    with events_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            rec = build_record(obj)
            if rec is not None:
                records.append(rec)

    tmp = out_path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as w:
        for rec in records:
            w.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tmp.replace(out_path)

    print(str(out_path))
    print(f"COUNT={len(records)}")


if __name__ == "__main__":
    main()
