"""
NEXT-TRADE-PMX-FILL-VERIFY-001
전수 스캔 + PnL 3자 대조 리포트
"""
import json, datetime
from pathlib import Path

EVENTS = Path("logs/runtime/profitmax_v1_events.jsonl")
FILLS  = Path("logs/runtime/trade_updates.jsonl")

# ── 이벤트 로드 ──────────────────────────────────────────────────────
events = []
for line in EVENTS.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    try:
        events.append(json.loads(line))
    except Exception:
        pass

run_starts = [e for e in events if e.get("event_type") == "RUN_START"]
last_start_ts = max(e["ts"] for e in run_starts)
print("Session start:", last_start_ts)

exits = [e for e in events
         if e.get("event_type") == "EXIT" and e["ts"] >= last_start_ts]
print("EXIT events  :", len(exits))

# EXIT orderId 추출
exit_map = {}
for ex in exits:
    p = ex.get("payload", {})
    eo = p.get("exit_order") or {}
    oid = str((eo.get("order") or {}).get("orderId", ""))
    if oid and oid != "0":
        exit_map[oid] = ex
print("EXIT orderIds:", len(exit_map))

# ── trade_updates 로드 ────────────────────────────────────────────────
fills_raw = []
for line in FILLS.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    try:
        fills_raw.append(json.loads(line))
    except Exception:
        pass

filled_by_oid = {}
for f in fills_raw:
    o = f.get("order", {})
    oid = str(o.get("order_id", ""))
    qty = float(f.get("fill", {}).get("qty", 0))
    if o.get("status") == "FILLED" and qty > 0:
        if oid not in filled_by_oid:
            filled_by_oid[oid] = f

# ── STEP 1: 전수 스캔 ─────────────────────────────────────────────────
print()
print("=" * 68)
print("STEP 1: EXIT orderId 전수 스캔 (FILLED 여부)")
print("=" * 68)
missing = []
for oid, ex in exit_map.items():
    p = ex["payload"]
    if oid in filled_by_oid:
        fi = filled_by_oid[oid].get("fill", {})
        mark = "FILLED"
        detail = "price=%s qty=%s tid=%s" % (fi.get("price"), fi.get("qty"), fi.get("trade_id"))
    else:
        mark = "MISSING"
        detail = "NOT IN trade_updates"
        missing.append(oid)
    print("  %-20s %-8s oid=%-14s %s" % (
        p.get("strategy_id", "?"), p.get("reason", "?"), oid, mark))
    if mark == "MISSING":
        print("    !! " + detail)

print()
if not missing:
    print(">> ALL FILLED OK (%d/%d)" % (len(exit_map), len(exit_map)))
else:
    print(">> MISSING: %d / %d" % (len(missing), len(exit_map)))

# ── STEP 2: PnL 3자 대조 ─────────────────────────────────────────────
start_epoch = datetime.datetime.fromisoformat(
    last_start_ts.replace("Z", "+00:00")
).timestamp() * 1000

A_pnl = sum(float(ex["payload"].get("pnl", 0)) for ex in exits)

B_fee = 0.0
B_count = 0
for f in fills_raw:
    ts = f.get("ts", 0)
    o = f.get("order", {})
    fi = f.get("fill", {})
    if ts >= start_epoch and o.get("status") == "FILLED" and float(fi.get("qty", 0)) > 0:
        B_fee += float(fi.get("fee", 0))
        B_count += 1

C_rpnl = 0.0
C_count = 0
for f in fills_raw:
    ts = f.get("ts", 0)
    rp = float(f.get("ledger", {}).get("realized_pnl", 0))
    if ts >= start_epoch and rp != 0.0:
        C_rpnl += rp
        C_count += 1

print()
print("=" * 68)
print("STEP 2: PnL 정합성 3자 대조 (세션 기준)")
print("=" * 68)
print("  (A) 엔진 EXIT pnl 합계   : %+.6f USDT  (%d건)" % (A_pnl, len(exits)))
print("  (B) fill fee 합계        : %+.6f USDT  (%d fills)" % (B_fee, B_count))
print("  (C) realized_pnl 합계   : %+.6f USDT  (%d non-zero)" % (C_rpnl, C_count))
print()
print("  (A - B)                 : %+.6f  [엔진pnl - fee]" % (A_pnl - B_fee))
print("  |A - C|                 : %.6f" % abs(A_pnl - C_rpnl))
print("  |(A-B) - C|             : %.6f" % abs((A_pnl - B_fee) - C_rpnl))
print()

diff_AC = abs(A_pnl - C_rpnl)
diff_AmBC = abs((A_pnl - B_fee) - C_rpnl)
if diff_AC < 0.05:
    print("  >> A ~ C: 엔진 pnl ~ Binance realized_pnl (fee 포함 일치)")
elif diff_AmBC < 0.05:
    print("  >> (A-B) ~ C: 엔진pnl - fee ~ Binance realized_pnl (fee 분리 일치)")
else:
    print("  >> 불일치 감지: A-C=%+.4f  (A-B)-C=%+.4f" % (
        A_pnl - C_rpnl, (A_pnl - B_fee) - C_rpnl))
    print("     -> 로깅/매핑 결함 또는 Binance realized_pnl 부분 누락 가능성")

# SSOT
ssot = None
ssot_ts = "-"
for e in reversed(events):
    v = e.get("payload", {}).get("session_realized_pnl")
    if v is not None:
        ssot = v
        ssot_ts = e["ts"]
        break
print()
print("  SSOT session_realized_pnl: %s USDT  (%s)" % (ssot, ssot_ts[:19]))

# surgery-003 트리거 체크
print()
print("=" * 68)
print("STEP 3: Surgery-003 트리거 조건 체크")
print("=" * 68)
issues = []
if missing:
    issues.append("CRITICAL: EXIT MISSING in trade_updates (%d개)" % len(missing))
if diff_AC > 0.1 and diff_AmBC > 0.1:
    issues.append("WARN: PnL 3자 불일치 큼 (|A-C|=%.4f)" % diff_AC)
# 최근 1h 창 pnl 체크
import time
now_epoch = time.time() * 1000
recent_exits = [e for e in exits if (now_epoch - 3600000) < (
    datetime.datetime.fromisoformat(e["ts"].replace("Z", "+00:00")).timestamp() * 1000
)]
recent_pnl = sum(float(e["payload"].get("pnl", 0)) for e in recent_exits)
recent_fee = sum(float(filled_by_oid.get(
    str((e["payload"].get("exit_order") or {}).get("order", {}).get("orderId", "")), {}
).get("fill", {}).get("fee", 0) * 2) for e in recent_exits)
print("  최근 1h: exits=%d  pnl=%+.4f  fee_est=%+.4f  net=%+.4f" % (
    len(recent_exits), recent_pnl, recent_fee, recent_pnl - recent_fee))
if recent_pnl - recent_fee < -0.3:
    issues.append("WARN: 최근 1h net(pnl-fee) 음수 지속 (%+.4f)" % (recent_pnl - recent_fee))

if not issues:
    print("  >> 트리거 조건 없음 — 현 세션 유지 관측 계속")
else:
    for iss in issues:
        print("  !! " + iss)
