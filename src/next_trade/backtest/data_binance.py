from __future__ import annotations

import csv
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

BINANCE_FAPI_KLINES = "https://fapi.binance.com/fapi/v1/klines"


def _cache_file(
    base_dir: Path,
    symbol: str,
    interval: str,
    days: int | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> Path:
    cache_dir = base_dir / "data" / "klines" / symbol / interval
    cache_dir.mkdir(parents=True, exist_ok=True)
    if start_ms is not None and end_ms is not None:
        return cache_dir / f"{symbol}_{interval}_{start_ms}_{end_ms}.csv"
    if days is None:
        raise ValueError("days must be provided when range mode is not used")
    return cache_dir / f"{symbol}_{interval}_{days}d.csv"


def _read_cache(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "open_time": int(row["open_time"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                    "close_time": int(row["close_time"]),
                }
            )
    return rows


def _write_cache(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["open_time", "open", "high", "low", "close", "volume", "close_time"],
        )
        writer.writeheader()
        writer.writerows(rows)


def _fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int) -> list[dict]:
    out: list[dict] = []
    cursor = start_ms
    while cursor < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": cursor,
            "endTime": end_ms,
            "limit": 1500,
        }
        response = requests.get(BINANCE_FAPI_KLINES, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        if not payload:
            break

        for k in payload:
            out.append(
                {
                    "open_time": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "close_time": int(k[6]),
                }
            )
        cursor = int(payload[-1][6]) + 1
        time.sleep(0.08)
    return out


def load_or_download_klines(
    project_root: Path,
    symbol: str = "BTCUSDT",
    interval: str = "15m",
    days: int = 60,
    start_ms: int | None = None,
    end_ms: int | None = None,
    force_refresh: bool = False,
) -> list[dict]:
    if (start_ms is None) ^ (end_ms is None):
        raise ValueError("Both start_ms and end_ms must be provided together")

    range_mode = (start_ms is not None) and (end_ms is not None)
    if range_mode and start_ms >= end_ms:
        raise ValueError("start_ms must be < end_ms")

    cache = _cache_file(
        project_root,
        symbol,
        interval,
        days=None if range_mode else days,
        start_ms=start_ms,
        end_ms=end_ms,
    )
    if cache.exists() and not force_refresh:
        rows = _read_cache(cache)
        if range_mode:
            return [r for r in rows if int(r["open_time"]) >= int(start_ms) and int(r["open_time"]) < int(end_ms)]
        return rows

    if range_mode:
        fetch_start_ms = int(start_ms)
        fetch_end_ms = int(end_ms)
    else:
        now = datetime.now(tz=timezone.utc)
        start = now - timedelta(days=days)
        fetch_start_ms = int(start.timestamp() * 1000)
        fetch_end_ms = int(now.timestamp() * 1000)

    rows = _fetch_klines(symbol=symbol, interval=interval, start_ms=fetch_start_ms, end_ms=fetch_end_ms)
    _write_cache(cache, rows)
    if range_mode:
        return [r for r in rows if int(r["open_time"]) >= int(start_ms) and int(r["open_time"]) < int(end_ms)]
    return rows


def ms_to_iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
