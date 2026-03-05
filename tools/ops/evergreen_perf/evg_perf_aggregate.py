import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


EVG_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen"
OUT_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf"


@dataclass
class Trade:
    ts: Optional[datetime]
    side: Optional[str]          # BUY/SELL (optional)
    pnl: float                   # realized pnl for the trade (or exit)
    r: Optional[float] = None    # optional R-multiple


def safe_float(x: str, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def compute_max_drawdown(equity_curve: List[float]) -> float:
    # returns max drawdown as positive number
    peak = float("-inf")
    max_dd = 0.0
    for e in equity_curve:
        if e > peak:
            peak = e
        dd = peak - e
        if dd > max_dd:
            max_dd = dd
    return max_dd


def try_parse_events_jsonl(evg_dir: Path) -> List[Trade]:
    """
    Best-effort: use profitmax_v1_events.jsonl if present.
    Expect lines with JSON; look for EXIT/TP/SL with realized_pnl fields or similar.
    This is intentionally tolerant: if schema differs, it will simply return fewer trades.
    """
    # priority: runtime SSOT -> evergreen local -> legacy patterns
    project_root = evg_dir.parent.parent if evg_dir.name.lower() == "evergreen" else Path(r"C:\projects\NEXT-TRADE")
    runtime_ssot = project_root / "logs" / "runtime" / "profitmax_v1_events.jsonl"

    candidates = []
    if runtime_ssot.exists():
        candidates.append(runtime_ssot)
    candidates.extend(list(evg_dir.rglob("profitmax_v1_events.jsonl")))
    candidates.extend(list(evg_dir.rglob("*events*.jsonl")))
    if not candidates:
        return []

    # de-dup and choose newest
    uniq = {}
    for c in candidates:
        uniq[str(c.resolve())] = c
    cand_list = list(uniq.values())
    cand_list.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    p = cand_list[0]

    trades: List[Trade] = []
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            et = (obj.get("event_type") or obj.get("type") or "").upper()

            # best-effort timestamp
            ts_raw = obj.get("ts") or obj.get("timestamp") or obj.get("time")
            ts = None
            if isinstance(ts_raw, str):
                try:
                    # allow ISO
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                    ts = ts.replace(tzinfo=None)
                except Exception:
                    ts = None

            payload = obj.get("payload") or obj.get("data") or obj

            # realized pnl extraction (common variants)
            pnl = None
            for k in ["realized_pnl", "pnl", "session_realized_pnl", "realizedPnl", "profit"]:
                v = payload.get(k) if isinstance(payload, dict) else None
                if isinstance(v, (int, float)):
                    pnl = float(v)
                    break
                if isinstance(v, str):
                    parsed = safe_float(v, None)
                    if parsed is not None:
                        pnl = float(parsed)
                        break

            # only treat certain events as "trade close" markers
            if et in ("EXIT", "TP", "SL") and pnl is not None:
                side = payload.get("side") if isinstance(payload, dict) else None
                trades.append(Trade(ts=ts, side=side, pnl=pnl))
    return trades


def try_parse_perf_trades(perf_trades_path: Path) -> List[Trade]:
    if not perf_trades_path.exists():
        return []
    trades: List[Trade] = []
    with perf_trades_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            pnl = obj.get("realized_pnl")
            if isinstance(pnl, str):
                pnl = safe_float(pnl, None)
            if not isinstance(pnl, (int, float)):
                continue
            ts = None
            ts_raw = obj.get("ts")
            if isinstance(ts_raw, str):
                try:
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    ts = None
            side = obj.get("side")
            trades.append(Trade(ts=ts, side=side, pnl=float(pnl)))
    return trades


def parse_session_60m_txt(evg_dir: Path) -> Dict[str, int]:
    # Sums event counts from session_60m_*.txt (ENTRY=, EXIT=, TP=, SL=, BLOCKED=)
    totals = {"ENTRY": 0, "EXIT": 0, "TP": 0, "SL": 0, "BLOCKED": 0}
    for p in evg_dir.glob("session_60m_*.txt"):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for k in totals.keys():
            m = re.search(rf"\b{k}=(\d+)\b", txt)
            if m:
                totals[k] += int(m.group(1))
    return totals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evg_dir", default=EVG_DIR_DEFAULT)
    ap.add_argument("--out_dir", default=OUT_DIR_DEFAULT)
    ap.add_argument("--timezone", default="KST")  # purely label for report
    args = ap.parse_args()

    evg_dir = Path(args.evg_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) event totals (coarse)
    event_totals = parse_session_60m_txt(evg_dir)

    # 2) trade-level pnl extraction (best-effort)
    perf_trades_path = evg_dir / "perf_trades.jsonl"
    trades = try_parse_perf_trades(perf_trades_path)
    trades_source = "PERF_TRADES" if trades else "EVENTS_JSONL"
    if not trades:
        trades = try_parse_events_jsonl(evg_dir)

    # Build equity curve from trades (cumulative pnl)
    equity = [0.0]
    for t in trades:
        equity.append(equity[-1] + t.pnl)

    total_pnl = equity[-1] if equity else 0.0
    max_dd = compute_max_drawdown(equity) if len(equity) > 1 else 0.0

    wins = sum(1 for t in trades if t.pnl > 0)
    losses = sum(1 for t in trades if t.pnl < 0)
    n = len(trades)

    winrate = (wins / n) if n else 0.0
    avg_win = (sum(t.pnl for t in trades if t.pnl > 0) / wins) if wins else 0.0
    avg_loss_abs = (abs(sum(t.pnl for t in trades if t.pnl < 0)) / losses) if losses else 0.0
    expectancy = (winrate * avg_win) - ((1 - winrate) * avg_loss_abs) if n else 0.0

    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss_abs = abs(sum(t.pnl for t in trades if t.pnl < 0))
    profit_factor = (gross_profit / gross_loss_abs) if gross_loss_abs > 0 else (float("inf") if gross_profit > 0 else 0.0)

    # Output json + txt summary
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = out_dir / f"perf_aggregate_{now}.json"
    out_txt = out_dir / f"perf_aggregate_{now}.txt"

    payload = {
        "stamp": f"EVG_PERF_{now}",
        "timezone_label": args.timezone,
        "source": {
            "evg_dir": str(evg_dir),
            "events_jsonl_trades_parsed": n,
            "trades_source": trades_source,
            "perf_trades_path": str(perf_trades_path),
        },
        "event_totals_from_session_60m": event_totals,
        "metrics": {
            "total_pnl": total_pnl,
            "max_drawdown": max_dd,
            "trades": n,
            "wins": wins,
            "losses": losses,
            "winrate": winrate,
            "avg_win": avg_win,
            "avg_loss_abs": avg_loss_abs,
            "expectancy": expectancy,
            "profit_factor": profit_factor,
            "gross_profit": gross_profit,
            "gross_loss_abs": gross_loss_abs,
        },
    }

    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = []
    lines.append(f"STAMP={payload['stamp']}")
    lines.append(f"TZ={payload['timezone_label']}")
    lines.append(f"TRADES={n} WINS={wins} LOSSES={losses} WINRATE={winrate:.4f}")
    lines.append(f"TOTAL_PNL={total_pnl:.8f}")
    lines.append(f"MAX_DD={max_dd:.8f}")
    lines.append(f"AVG_WIN={avg_win:.8f} AVG_LOSS_ABS={avg_loss_abs:.8f}")
    lines.append(f"EXPECTANCY={expectancy:.8f}")
    lines.append(f"PROFIT_FACTOR={profit_factor if profit_factor != float('inf') else 'INF'}")
    lines.append(f"EVENT_TOTALS={json.dumps(event_totals, ensure_ascii=False)}")
    lines.append("NOTE=trade-level pnl is best-effort from events jsonl; counts are from session_60m files.")
    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(str(out_txt))


if __name__ == "__main__":
    main()
