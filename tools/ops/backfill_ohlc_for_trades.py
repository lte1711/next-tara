import argparse
import json
import math
import os
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


DEFAULT_TRADES = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf_trades.jsonl"
DEFAULT_OUT_DIR = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf"
DEFAULT_BASE_URL = "https://demo-fapi.binance.com"
INTERVAL_MS = 5 * 60 * 1000


def _to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _parse_iso_to_ms(v: str) -> int | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def _floor_5m_ms(ts_ms: int) -> int:
    return (ts_ms // INTERVAL_MS) * INTERVAL_MS


def _ms_to_iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).isoformat()


def _fetch_klines(base_url: str, symbol: str, end_time_ms: int, limit: int = 60):
    q = urlencode(
        {
            "symbol": symbol,
            "interval": "5m",
            "endTime": end_time_ms,
            "limit": limit,
        }
    )
    url = f"{base_url.rstrip('/')}/fapi/v1/klines?{q}"
    with urlopen(url, timeout=10) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    return json.loads(raw)


def _build_ha(ohlc):
    out = []
    prev_ha_open = None
    prev_ha_close = None
    for o, h, l, c in ohlc:
        ha_close = (o + h + l + c) / 4.0
        if prev_ha_open is None or prev_ha_close is None:
            ha_open = (o + c) / 2.0
        else:
            ha_open = (prev_ha_open + prev_ha_close) / 2.0
        ha_high = max(h, ha_open, ha_close)
        ha_low = min(l, ha_open, ha_close)
        out.append((ha_open, ha_high, ha_low, ha_close))
        prev_ha_open, prev_ha_close = ha_open, ha_close
    return out


def _calc_meta(klines):
    # kline: [openTime, open, high, low, close, volume, closeTime, ...]
    if not isinstance(klines, list) or len(klines) < 20:
        return None, "insufficient_bars"

    ohlc = []
    closes = []
    for k in klines:
        o = _to_float(k[1], None)
        h = _to_float(k[2], None)
        l = _to_float(k[3], None)
        c = _to_float(k[4], None)
        if None in (o, h, l, c):
            return None, "calc_error"
        ohlc.append((o, h, l, c))
        closes.append(c)

    try:
        ha = _build_ha(ohlc)
        ha_open, ha_high, ha_low, ha_close = ha[-1]
        body = ha_close - ha_open
        if body > 0:
            ha_dir = "UP"
        elif body < 0:
            ha_dir = "DOWN"
        else:
            ha_dir = "FLAT"
        span = max(ha_high - ha_low, 1e-9)
        ha_strength = max(0.0, min(100.0, abs(body) / span * 100.0))

        window = closes[-20:]
        mid = sum(window) / 20.0
        std = statistics.pstdev(window) if len(window) > 1 else 0.0
        upper = mid + (2.0 * std)
        lower = mid - (2.0 * std)
        last = closes[-1]
        if last > upper:
            bb_pos = "ABOVE_UPPER"
        elif last < lower:
            bb_pos = "BELOW_LOWER"
        elif last >= mid:
            bb_pos = "ABOVE_MID"
        else:
            bb_pos = "BELOW_MID"
        bb_width = (upper - lower) / mid if mid != 0 else 0.0
        sq_th = _to_float(os.getenv("NEXTTRADE_BB_SQUEEZE_WIDTH_TH", "0.008"), 0.008)
        bb_squeeze = "YES" if bb_width <= sq_th else "NO"
    except Exception:
        return None, "calc_error"

    return {
        "ha_trend_dir": ha_dir,
        "ha_trend_strength": round(ha_strength, 4),
        "bb_pos": bb_pos,
        "bb_width": round(bb_width, 8),
        "bb_squeeze": bb_squeeze,
    }, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", default=DEFAULT_TRADES)
    ap.add_argument("--out_dir", default=DEFAULT_OUT_DIR)
    ap.add_argument(
        "--base_url",
        default=os.getenv("BINANCE_TESTNET_BASE_URL", DEFAULT_BASE_URL),
    )
    args = ap.parse_args()

    trades_path = Path(args.trades)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not trades_path.exists():
        print("ERROR=trades_file_missing")
        return

    rows = []
    with trades_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue

    cache = {}
    now_ms = int(time.time() * 1000)
    reason_counts = Counter()
    patched = 0

    for r in rows:
        symbol = str(r.get("symbol") or "BTCUSDT")
        ts_ms = _parse_iso_to_ms(str(r.get("ha_bb_bar_close_ts") or ""))
        if ts_ms is None:
            ts_ms = _parse_iso_to_ms(str(r.get("ts_exit") or r.get("ts") or ""))
            if ts_ms is not None:
                ts_ms = _floor_5m_ms(ts_ms)
        if ts_ms is None:
            reason = "calc_error"
            r["ha_trend_dir"] = "UNKNOWN"
            r["ha_trend_strength"] = None
            r["bb_pos"] = "UNKNOWN"
            r["bb_width"] = None
            r["bb_squeeze"] = "UNKNOWN"
            r["ha_bb_reason"] = reason
            r["ha_bb_bar_close_ts"] = ""
            reason_counts[reason] += 1
            continue

        if ts_ms + INTERVAL_MS > now_ms:
            reason = "bar_not_closed"
            r["ha_trend_dir"] = "UNKNOWN"
            r["ha_trend_strength"] = None
            r["bb_pos"] = "UNKNOWN"
            r["bb_width"] = None
            r["bb_squeeze"] = "UNKNOWN"
            r["ha_bb_reason"] = reason
            r["ha_bb_bar_close_ts"] = _ms_to_iso(ts_ms)
            reason_counts[reason] += 1
            continue

        key = (symbol, ts_ms)
        if key not in cache:
            try:
                # Include target closed bar in window: endTime = close_ts + 1ms.
                cache[key] = _fetch_klines(args.base_url, symbol, ts_ms + INTERVAL_MS + 1, limit=60)
            except Exception:
                cache[key] = None

        kl = cache[key]
        if not kl:
            reason = "no_ohlc_source"
            r["ha_trend_dir"] = "UNKNOWN"
            r["ha_trend_strength"] = None
            r["bb_pos"] = "UNKNOWN"
            r["bb_width"] = None
            r["bb_squeeze"] = "UNKNOWN"
            r["ha_bb_reason"] = reason
            r["ha_bb_bar_close_ts"] = _ms_to_iso(ts_ms)
            reason_counts[reason] += 1
            continue

        meta, reason = _calc_meta(kl)
        if meta is None:
            r["ha_trend_dir"] = "UNKNOWN"
            r["ha_trend_strength"] = None
            r["bb_pos"] = "UNKNOWN"
            r["bb_width"] = None
            r["bb_squeeze"] = "UNKNOWN"
            r["ha_bb_reason"] = reason
            r["ha_bb_bar_close_ts"] = _ms_to_iso(ts_ms)
            reason_counts[reason] += 1
            continue

        r.update(meta)
        r["ha_bb_reason"] = ""
        r["ha_bb_bar_close_ts"] = _ms_to_iso(ts_ms)
        patched += 1

    tmp = trades_path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as w:
        for r in rows:
            w.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(trades_path)

    total = len(rows)
    unknown = 0
    for r in rows:
        if (
            str(r.get("ha_trend_dir") or "").upper() == "UNKNOWN"
            or str(r.get("bb_pos") or "").upper() == "UNKNOWN"
            or str(r.get("bb_squeeze") or "").upper() == "UNKNOWN"
        ):
            unknown += 1

    unknown_rate = (unknown / total * 100.0) if total else 0.0
    meta_present = 0
    for r in rows:
        if all(
            k in r
            for k in (
                "ha_trend_dir",
                "ha_trend_strength",
                "bb_pos",
                "bb_width",
                "bb_squeeze",
                "ha_bb_reason",
                "ha_bb_bar_close_ts",
            )
        ):
            meta_present += 1
    meta_rate = (meta_present / total * 100.0) if total else 0.0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rpt = out_dir / "ha_bb_meta_quality_backfilled.txt"
    rpt_ts = out_dir / f"ha_bb_meta_quality_backfilled_{stamp}.txt"
    lines = [
        f"STAMP=HA_BB_BACKFILL_{stamp}",
        f"TRADES_TOTAL={total}",
        f"PATCHED_COUNT={patched}",
        f"META_PRESENT_RATE={meta_rate:.2f}%",
        f"UNKNOWN_RATE={unknown_rate:.2f}%",
        f"UNKNOWN_REASON_BREAKDOWN={json.dumps(dict(reason_counts), ensure_ascii=False)}",
    ]
    txt = "\n".join(lines) + "\n"
    rpt.write_text(txt, encoding="utf-8")
    rpt_ts.write_text(txt, encoding="utf-8")
    print(str(rpt))
    print(str(rpt_ts))


if __name__ == "__main__":
    main()

