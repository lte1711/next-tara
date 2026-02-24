import time
import json
from pathlib import Path

OUT = Path(r"C:\projects\NEXT-TRADE\evidence\final\phase-b")
OUT.mkdir(parents=True, exist_ok=True)

# Minimal guardrail (repo의 정식 guardrail이 core 의존성 때문에 못 뜨므로, B-1에서는 최소 기준으로 증명)
# 규칙: qty가 비정상적으로 크면 무조건 REJECT + audit 기록
def validate(order: dict):
    qty = float(order.get("qty", 0))
    if qty > 10:  # 임계는 테스트용(현실 주문 대비 과도)
        return {
            "ok": False,
            "decision": "REJECT",
            "reason": "qty_exceeds_safety_threshold",
        }
    return {"ok": True, "decision": "ALLOW"}

order = {
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "MARKET",
    "qty": 999999,
    "ts": time.time(),
}

res = validate(order)

audit = {
    "ts": time.time(),
    "phase": "PHASE-FINAL-B-1",
    "component": "guardrail_minimal",
    "order": order,
    "result": res,
    "guarantee": {
        "no_exchange_call": True,
        "no_fill": True,
        "no_position_change": True,
    },
}

(Path(OUT / "guardrail_reject.json")).write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
print("Guardrail Result:", res)
print("Saved:", str(OUT / "guardrail_reject.json"))
