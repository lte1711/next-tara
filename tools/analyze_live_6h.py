"""
LIVE-PROFITFIX-001: 전략/레짐별 손익 분리 분석
대상 세션:
  Session1: 2026-02-26T20:00:45 ~ 2026-02-27T02:00:48 UTC
  Session2: 2026-02-27T02:00:53 ~ 2026-02-27T08:00:58 UTC
"""
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

EVENTS_FILE   = Path("C:/projects/NEXT-TRADE/logs/runtime/profitmax_v1_events.jsonl")
FILLS_FILE    = Path("C:/projects/NEXT-TRADE/logs/runtime/trade_updates.jsonl")

# 세션 경계 (UTC epoch)
SESSION1_START = datetime(2026, 2, 26, 20, 0, 45, tzinfo=timezone.utc).timestamp()
SESSION1_END   = datetime(2026, 2, 27,  2, 0, 50, tzinfo=timezone.utc).timestamp()
SESSION2_START = datetime(2026, 2, 27,  2, 0, 53, tzinfo=timezone.utc).timestamp()
SESSION2_END   = datetime(2026, 2, 27,  8, 1,  0, tzinfo=timezone.utc).timestamp()

def parse_ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except:
        try:
            v = float(s)
            return v / 1000 if v > 1e12 else v
        except:
            return 0.0

# ── 1. fills: order_id → total_fee 매핑 ──────────────────────────────────────
fills_fee = {}  # order_id → fee (exit fill only)
for line in FILLS_FILE.read_text(encoding="utf-8").splitlines():
    if not line.strip(): continue
    try:
        r = json.loads(line)
        f = r.get("fill", {})
        qty = float(f.get("qty", 0))
        if qty <= 0: continue
        oid = str(f.get("order_id", ""))
        fee = float(f.get("fee", 0))
        if oid:
            fills_fee[oid] = fills_fee.get(oid, 0.0) + fee
    except:
        continue

# ── 2. events 파싱: EXIT + HEARTBEAT ─────────────────────────────────────────
exits      = []
heartbeats = []  # [(ts_epoch, regime)]

for line in EVENTS_FILE.read_text(encoding="utf-8").splitlines():
    if not line.strip(): continue
    try:
        r = json.loads(line)
        et  = r.get("event_type", "")
        ts  = parse_ts(r.get("ts", 0))
        pay = r.get("payload", {})

        if et == "HEARTBEAT":
            regime = pay.get("regime", "unknown")
            heartbeats.append((ts, regime))

        elif et == "EXIT":
            exit_order_obj = (pay.get("exit_order") or {}).get("order") or {}
            oid = str(exit_order_obj.get("orderId", ""))
            exits.append({
                "ts"          : ts,
                "strategy_id" : pay.get("strategy_id", "unknown"),
                "reason"      : pay.get("reason", ""),
                "pnl"         : float(pay.get("pnl", 0)),
                "exit_oid"    : oid,
            })
    except:
        continue

heartbeats.sort(key=lambda x: x[0])

# ── 3. 각 EXIT에 레짐 부여 (직전 HEARTBEAT) ──────────────────────────────────
def get_regime(ts_epoch):
    regime = "unknown"
    for hb_ts, hb_regime in heartbeats:
        if hb_ts <= ts_epoch:
            regime = hb_regime
        else:
            break
    return regime

# ── 4. 6h 세션 범위 필터 + 집계 ─────────────────────────────────────────────
stats = defaultdict(lambda: {
    "trades": 0, "wins": 0,
    "gross_pnl": 0.0, "fees": 0.0,
    "timestamps": []
})

in_session = 0
for ex in exits:
    ts = ex["ts"]
    in_s1 = SESSION1_START <= ts <= SESSION1_END
    in_s2 = SESSION2_START <= ts <= SESSION2_END
    if not (in_s1 or in_s2):
        continue

    in_session += 1
    regime = get_regime(ts)
    key = (ex["strategy_id"], regime)

    # 수수료: exit fill 확정 + entry fill 추정(동일 qty/가격 ≈ 동일 fee)
    exit_fee  = fills_fee.get(ex["exit_oid"], 0.0)
    total_fee = exit_fee * 2  # entry fee 추정 = exit fee

    stats[key]["trades"]    += 1
    stats[key]["wins"]      += 1 if ex["pnl"] > 0 else 0
    stats[key]["gross_pnl"] += ex["pnl"]
    stats[key]["fees"]      += total_fee
    stats[key]["timestamps"].append(ts)

# ── 5. 결과 출력 ─────────────────────────────────────────────────────────────
rows = []
for (strategy, regime), s in stats.items():
    trades = s["trades"]
    wins   = s["wins"]
    wr     = wins / trades * 100 if trades else 0
    gross  = s["gross_pnl"]
    fees   = s["fees"]
    net    = gross - fees

    ts_list = sorted(s["timestamps"])
    if len(ts_list) > 1:
        diffs = [(ts_list[i+1] - ts_list[i]) / 60 for i in range(len(ts_list)-1)]
        avg_int = sum(diffs) / len(diffs)
    else:
        avg_int = 0.0

    rows.append((strategy, regime, trades, wr, gross, fees, net, avg_int))

rows.sort(key=lambda x: x[6])  # NetPnL 오름차순

# ── 표 출력 ──────────────────────────────────────────────────────────────────
HDR = f"{'Strategy':<20} {'Regime':<10} {'Trades':>6} {'WinRate%':>9} {'GrossPnL':>10} {'Fees':>9} {'NetPnL':>10} {'AvgIntMin':>10}"
print(HDR)
print("─" * len(HDR))
for r in rows:
    print(f"{r[0]:<20} {r[1]:<10} {r[2]:>6} {r[3]:>8.1f}% {r[4]:>10.4f} {r[5]:>9.4f} {r[6]:>10.4f} {r[7]:>9.1f}")

print()
total_trades = sum(r[2] for r in rows)
total_gross  = sum(r[4] for r in rows)
total_fees   = sum(r[5] for r in rows)
total_net    = sum(r[6] for r in rows)
print(f"TOTAL  {'':10} {total_trades:>6} {'':>9}  {total_gross:>10.4f} {total_fees:>9.4f} {total_net:>10.4f}")

# ── 5줄 요약 ─────────────────────────────────────────────────────────────────
worst = min(rows, key=lambda x: x[6])
best  = max(rows, key=lambda x: x[6])
fee_dominated = [(r[0], r[1]) for r in rows if r[4] > 0 and r[6] < 0]

print()
print("=" * 60)
print("【5줄 요약】")
print(f"1. NetPnL 최악: {worst[0]} / {worst[1]} → {worst[6]:.4f} USDT")
print(f"2. NetPnL 최고: {best[0]} / {best[1]} → {best[6]:.4f} USDT")
print(f"3. 전체 Trades: {total_trades}건 (6h 세션1+2 합산)")
print(f"4. 전체 Fees 합: {total_fees:.4f} USDT")
fd_str = str(fee_dominated) if fee_dominated else "없음"
print(f"5. 수수료 지배형(GrossPnL>0 & NetPnL<0): {fd_str}")
print("=" * 60)
print(f"\n※ 전체 세션 EXIT 건수: {in_session}건 (6h 세션1+2 내)")
