import argparse
from datetime import datetime
from pathlib import Path


PERF_DIR_DEFAULT = r"C:\projects\NEXT-TRADE\evidence\evergreen\perf"


def _latest(perf_dir: Path, pattern: str) -> Path | None:
    files = sorted(perf_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _read_kv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _to_float(v: str, default: float = 0.0) -> float:
    try:
        return float(v.replace("%", ""))
    except Exception:
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perf_dir", default=PERF_DIR_DEFAULT)
    args = ap.parse_args()

    perf_dir = Path(args.perf_dir)
    perf_dir.mkdir(parents=True, exist_ok=True)

    reg = _latest(perf_dir, "ph7c_daily_regression_*.txt")
    if not reg:
        out = perf_dir / f"ph7c_alert_hits_{datetime.now().strftime('%Y%m%d')}.txt"
        out.write_text(
            "DATE_KST=\nA1_DATA_PIPELINE_HITS=0\nA2_GUARD_OVERBLOCK_HITS=0\nA3_SHADOW_SCORE_RISK_HITS=0\nA4_DD_SIM_DIVERGENCE_HITS=0\nNOTE=alert-only; no blocking\n",
            encoding="utf-8",
        )
        print(str(out))
        return

    kv = _read_kv(reg)

    unknown_rate = _to_float(kv.get("UNKNOWN_RATE_LAST_24H", "0"))
    low = _to_float(kv.get("REPLAY_LOW_SCORE_PNL_SUM", "0"))
    high = _to_float(kv.get("REPLAY_HIGH_SCORE_PNL_SUM", "0"))

    # A1: unknown rate > 5%
    a1 = 1 if unknown_rate > 5.0 else 0

    # A2: guard overblock requires explicit guard_block_rate (not in current regression, default no hit)
    a2 = 0

    # A3: shadow score risk proxy: if low-score pnl dominates high-score pnl (conservative proxy)
    a3 = 1 if (low > high and abs(low) > 0) else 0

    # A4: dd divergence requires sim_worst_dd/real_dd pair (not in current regression, default no hit)
    a4 = 0

    out = perf_dir / f"ph7c_alert_hits_{datetime.now().strftime('%Y%m%d')}.txt"
    lines = [
        f"DATE_KST={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"SOURCE_REGRESSION={reg}",
        f"A1_DATA_PIPELINE_HITS={a1}",
        f"A2_GUARD_OVERBLOCK_HITS={a2}",
        f"A3_SHADOW_SCORE_RISK_HITS={a3}",
        f"A4_DD_SIM_DIVERGENCE_HITS={a4}",
        "NOTE=alert-only; no blocking",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()
