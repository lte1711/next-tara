"""
Session 4 관측 리포트 생성기
Directive: NEXT-TRADE-LIVE-SESSION4-HONEY-001

사용법:
  python tools/analyze_session4.py              # 현재 Session 4 기준으로 실행
  python tools/analyze_session4.py --stamp      # 스냅샷 저장 포함

비교 기준(Session 1+2 평균):
  - 거래 빈도: 43건/12h = 3.58건/h
  - 수수료:    4.6334 USDT/12h = 0.386 USDT/h
  - NetPnL:   -7.4634 USDT/12h = -0.622 USDT/h
"""

import argparse
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

EVENTS_FILE = Path("C:/projects/NEXT-TRADE/logs/runtime/profitmax_v1_events.jsonl")
SUMMARY_FILE = Path("C:/projects/NEXT-TRADE/logs/runtime/profitmax_v1_summary.json")
FILLS_FILE = Path("C:/projects/NEXT-TRADE/logs/runtime/trade_updates.jsonl")
STAMP_DIR = Path("C:/projects/NEXT-TRADE/evidence/phase-live-session4/STAMP")

# Session 1+2 기준 (12h 합산)
BASELINE = {
    "hours": 12.0,
    "trades": 43,
    "fees_total": 4.6334,
    "net_pnl": -7.4634,
    "fee_per_hour": 4.6334 / 12,
    "trades_per_hour": 43 / 12,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(s: str) -> float:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def load_events():
    if not EVENTS_FILE.exists():
        return []
    lines = EVENTS_FILE.read_text(encoding="utf-8").splitlines()
    events = []
    for line in lines:
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    return events


def find_session4_start(events):
    """가장 마지막 RUN_START 타임스탬프를 Session 4 시작으로 인식"""
    run_starts = [e for e in events if e.get("event_type") == "RUN_START"]
    if not run_starts:
        return None
    last = max(run_starts, key=lambda e: parse_ts(e.get("ts", 0)))
    return parse_ts(last.get("ts", 0))


def load_fills_fee():
    """order_id → fee 매핑 (exit fill 기준)"""
    if not FILLS_FILE.exists():
        return {}
    fees = {}
    for line in FILLS_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            f = r.get("fill", {})
            qty = float(f.get("qty", 0))
            if qty <= 0:
                continue
            oid = str(f.get("order_id", ""))
            fee = float(f.get("fee", 0))
            if oid:
                fees[oid] = fees.get(oid, 0.0) + fee
        except Exception:
            continue
    return fees


def analyze(stamp: bool = False):
    events = load_events()
    if not events:
        print("❌ events 파일 없음 또는 비어 있음")
        return

    session4_start_ts = find_session4_start(events)
    if session4_start_ts is None:
        print("❌ RUN_START 이벤트 없음")
        return

    session4_start_dt = datetime.fromtimestamp(session4_start_ts, tz=timezone.utc)
    now_ts = utc_now().timestamp()
    elapsed_hours = (now_ts - session4_start_ts) / 3600

    # Session 4 범위 이벤트만 필터
    s4_events = [
        e for e in events
        if parse_ts(e.get("ts", 0)) >= session4_start_ts
    ]

    # ── 1. STRATEGY_BLOCKED 집계 ─────────────────────────────────────────────
    blocked_range = 0      # Surgery-001: range regime entry blocked
    blocked_edge = 0       # Surgery-001: min_edge_gate
    blocked_other = 0

    for e in s4_events:
        if e.get("event_type") != "STRATEGY_BLOCKED":
            continue
        reason = e.get("payload", {}).get("reason", "")
        if "range regime entry blocked" in reason:
            blocked_range += 1
        elif "min_edge_gate" in reason:
            blocked_edge += 1
        else:
            blocked_other += 1

    blocked_total = blocked_range + blocked_edge + blocked_other

    # ── 2. ENTRY/EXIT 집계 ───────────────────────────────────────────────────
    fills_fee = load_fills_fee()

    entries = [e for e in s4_events if e.get("event_type") == "ENTRY"]
    exits = [e for e in s4_events if e.get("event_type") == "EXIT"]

    gross_pnl = 0.0
    fees_total = 0.0
    wins = 0
    by_strategy: dict = defaultdict(lambda: {"trades": 0, "wins": 0, "gross": 0.0, "fees": 0.0})

    for ex in exits:
        pay = ex.get("payload", {})
        pnl = float(pay.get("pnl", 0))
        sid = pay.get("strategy_id", "unknown")
        exit_oid = str(
            (pay.get("exit_order") or {}).get("order", {}).get("orderId", "")
        )
        exit_fee = fills_fee.get(exit_oid, 0.0)
        total_fee = exit_fee * 2

        gross_pnl += pnl
        fees_total += total_fee
        by_strategy[sid]["trades"] += 1
        by_strategy[sid]["gross"] += pnl
        by_strategy[sid]["fees"] += total_fee
        if pnl > 0:
            wins += 1
            by_strategy[sid]["wins"] += 1

    trades = len(exits)
    net_pnl = gross_pnl - fees_total
    win_rate = wins / trades * 100 if trades else 0

    # 시간당 지표
    fee_per_hour = fees_total / elapsed_hours if elapsed_hours > 0 else 0
    trades_per_hour = trades / elapsed_hours if elapsed_hours > 0 else 0

    # ── 3. Shadow PnL 추정 (range에서 막힌 손실) ─────────────────────────────
    # 차단된 이벤트가 실제로 진입 → Session 1+2의 mean_reversion/range 평균 손실 적용
    # S1+2: mean_reversion/range NetPnL = -6.5243 / 40거래 = -0.163 USDT/거래
    shadow_loss_per_trade = -6.5243 / 40  # = -0.1631
    shadow_pnl_saved = blocked_range * abs(shadow_loss_per_trade)

    # ── 4. 출력 ──────────────────────────────────────────────────────────────
    print("=" * 65)
    print("  SESSION 4 관측 리포트 (Surgery-001 적용 후)")
    print("=" * 65)
    print(f"  Session 4 시작  : {session4_start_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"  현재 경과       : {elapsed_hours:.1f}h")
    print()

    print("【1. STRATEGY_BLOCKED 집계】")
    print(f"  range regime 차단   : {blocked_range:>5}건  (mean_reversion/trend_momentum)")
    print(f"  min_edge_gate 차단  : {blocked_edge:>5}건")
    print(f"  기타                : {blocked_other:>5}건")
    print(f"  합계                : {blocked_total:>5}건")
    if blocked_total > 0:
        edge_pct = blocked_edge / blocked_total * 100
        print(f"  → min_edge_gate 비율: {edge_pct:.1f}%  (90% 초과 시 임계값 재조정 검토)")
    print()

    print("【2. 실제 거래 현황】")
    print(f"  ENTRY 이벤트  : {len(entries):>4}건")
    print(f"  EXIT  이벤트  : {trades:>4}건")
    print(f"  WinRate       : {win_rate:>6.1f}%")
    print(f"  GrossPnL      : {gross_pnl:>9.4f} USDT")
    print(f"  Fees (추정)   : {fees_total:>9.4f} USDT")
    print(f"  NetPnL        : {net_pnl:>9.4f} USDT")
    print()

    if by_strategy:
        print("  전략별 내역:")
        print(f"  {'Strategy':<22} {'Trades':>6} {'WR%':>6} {'GrossPnL':>10} {'Fees':>8} {'NetPnL':>10}")
        print("  " + "-" * 65)
        for sid, s in sorted(by_strategy.items(), key=lambda x: x[1]["gross"] - x[1]["fees"]):
            wr = s["wins"] / s["trades"] * 100 if s["trades"] else 0
            net = s["gross"] - s["fees"]
            print(f"  {sid:<22} {s['trades']:>6} {wr:>5.1f}% {s['gross']:>10.4f} {s['fees']:>8.4f} {net:>10.4f}")
        print()

    print("【3. 시간당 비교 (vs Session 1+2 기준)】")
    print(f"  {'지표':<22} {'Session 1+2 기준':>16} {'Session 4':>12} {'개선률':>8}")
    print("  " + "-" * 62)
    _cmp("거래 빈도 (건/h)", BASELINE["trades_per_hour"], trades_per_hour)
    _cmp("수수료 (USDT/h)", BASELINE["fee_per_hour"], fee_per_hour)
    print()

    print("【4. Shadow PnL (막힌 손실 추정)】")
    print(f"  range 차단 건수     : {blocked_range}건")
    print(f"  S1+2 평균 손실/거래 : {shadow_loss_per_trade:.4f} USDT")
    print(f"  추정 절감액 (하한)  : +{shadow_pnl_saved:.4f} USDT (수술 덕분에 아낀 손실)")
    print()

    # ── 5. Summary JSON 읽기 ──────────────────────────────────────────────────
    if SUMMARY_FILE.exists():
        summary = json.loads(SUMMARY_FILE.read_text(encoding="utf-8"))
        ssot_pnl = summary.get("session_realized_pnl", "N/A")
        print("【5. ProfitMax SSOT PnL】")
        print(f"  session_realized_pnl : {ssot_pnl} USDT")
        print()

    # ── 6. GO/NO-GO 간단 판정 ────────────────────────────────────────────────
    print("【6. GO/NO-GO 초기 판정】")
    issues = []
    if blocked_edge > 0 and blocked_total > 0 and (blocked_edge / blocked_total) > 0.9:
        issues.append("⚠️  min_edge_gate 비율 90% 초과 → 임계값 재조정 검토")
    if trades_per_hour > BASELINE["trades_per_hour"]:
        issues.append("⚠️  거래 빈도 증가 (개선 없음)")
    if elapsed_hours > 0 and trades == 0 and blocked_total == 0:
        issues.append("❌ 이벤트 없음 → 엔진 미동작 의심")

    if not issues:
        print("  ✅ 초기 지표 정상 — 계속 관측")
    else:
        for iss in issues:
            print(f"  {iss}")

    print("=" * 65)

    # ── 7. 스냅샷 저장 ───────────────────────────────────────────────────────
    if stamp:
        ts_tag = utc_now().strftime("%Y%m%d_%H%M%S")
        stamp_path = STAMP_DIR / ts_tag
        stamp_path.mkdir(parents=True, exist_ok=True)

        for src in [EVENTS_FILE, SUMMARY_FILE, FILLS_FILE]:
            if src.exists():
                shutil.copy2(src, stamp_path / src.name)

        print(f"\n📸 스냅샷 저장: {stamp_path}")


def _cmp(label: str, baseline: float, actual: float):
    if baseline > 0:
        improvement = (baseline - actual) / baseline * 100
        arrow = "▼" if actual < baseline else "▲"
        print(f"  {label:<22} {baseline:>16.3f} {actual:>12.3f} {arrow}{abs(improvement):>6.1f}%")
    else:
        print(f"  {label:<22} {baseline:>16.3f} {actual:>12.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Session 4 관측 리포트")
    parser.add_argument("--stamp", action="store_true", help="스냅샷 저장")
    args = parser.parse_args()
    analyze(stamp=args.stamp)
