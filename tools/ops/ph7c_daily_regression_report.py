import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path


PERF_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf"
TRADES_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf_trades.jsonl"
OUT_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf"


def _to_float(v: str, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _latest_file(perf_dir: Path, pattern: str) -> Path | None:
    files = sorted(perf_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _read_key_values(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _task_last_result(task_name: str) -> str:
    def _query(name: str) -> str:
        r = subprocess.run(
            ["schtasks", "/Query", "/TN", name, "/V", "/FO", "LIST"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=10,
        )
        if r.returncode != 0:
            return ""
        for line in r.stdout.splitlines():
            if "Last Result:" in line:
                return line.split(":", 1)[1].strip()
        return ""

    try:
        res = _query(task_name)
        if res:
            return res
        # fallback: try without leading backslash
        res = _query(task_name.lstrip("\\"))
        if res:
            return res
    except Exception:
        return "ERR"
    return "UNKNOWN"


def _last24h_trade_stats(trades_path: Path) -> tuple[int, float]:
    if not trades_path.exists():
        return 0, 0.0
    now = datetime.now().astimezone()
    since = now - timedelta(hours=24)
    total = 0
    unknown = 0
    with trades_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            ts = str(r.get("ts_exit") or r.get("ts") or "")
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
            except Exception:
                continue
            if dt < since:
                continue
            total += 1
            if (
                str(r.get("ha_trend_dir") or "").upper() == "UNKNOWN"
                or str(r.get("bb_pos") or "").upper() == "UNKNOWN"
                or str(r.get("bb_squeeze") or "").upper() == "UNKNOWN"
            ):
                unknown += 1
    unknown_rate = (unknown / total * 100.0) if total > 0 else 0.0
    return total, unknown_rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perf_dir", default=PERF_DIR_DEFAULT)
    ap.add_argument("--trades", default=TRADES_DEFAULT)
    ap.add_argument("--out_dir", default=OUT_DIR_DEFAULT)
    args = ap.parse_args()

    perf_dir = Path(args.perf_dir)
    trades_path = Path(args.trades)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    v2_txt = _latest_file(perf_dir, "phase7c_shadow_scoring_table_v2_*.txt")
    replay = _latest_file(perf_dir, "phase7c_shadow_replay_*.txt")

    v2 = _read_key_values(v2_txt) if v2_txt else {}
    rp = _read_key_values(replay) if replay else {}

    trades_24h, unknown_rate_24h = _last24h_trade_stats(trades_path)
    corr_last = _task_last_result(r"\NEXTTRADE_EVG_REGIME_SIGNAL_CORR_60M")
    guard_last = _task_last_result(r"\NEXTTRADE_EVG_MR_GUARD_SIM_DAILY")

    day = datetime.now().strftime("%Y%m%d")
    out = out_dir / f"ph7c_daily_regression_{day}.txt"
    lines = [
        f"DATE_KST={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"TRADES_TOTAL_LAST_24H={trades_24h}",
        f"UNKNOWN_RATE_LAST_24H={unknown_rate_24h:.2f}%",
        f"RULES_WITH_NONZERO_WEIGHT={v2.get('RULES_WITH_NONZERO_WEIGHT', 'NA')}",
        f"MAX_WEIGHT={v2.get('MAX_WEIGHT', 'NA')}",
        f"WEIGHT_SUM={v2.get('WEIGHT_SUM', 'NA')}",
        f"REPLAY_LOW_SCORE_PNL_SUM={rp.get('LOW_SCORE_PNL_SUM', 'NA')}",
        f"REPLAY_HIGH_SCORE_PNL_SUM={rp.get('HIGH_SCORE_PNL_SUM', 'NA')}",
        f"SCHEDULE_LAST_RESULT_CORR={corr_last}",
        f"SCHEDULE_LAST_RESULT_GUARD={guard_last}",
        "ENGINE_APPLY_STATUS=DISABLED",
        f"SOURCE_V2={v2_txt if v2_txt else ''}",
        f"SOURCE_REPLAY={replay if replay else ''}",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()
