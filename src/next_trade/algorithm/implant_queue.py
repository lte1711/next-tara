from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from .evidence_miner import mine_patterns
from .risk_validator import validate
from .strategy_composer import compose_strategy

ROOT = Path(r"C:\projects\NEXT-TRADE")
OUT_FILE = ROOT / "evidence" / "analysis" / "implant_queue.json"
VALIDATION_FILE = ROOT / "evidence" / "analysis" / "strategy_validation_report.json"
TABLE_FILE = ROOT / "evidence" / "analysis" / "shadow_strategy_table.json"


def build_queue(out_file: Path = OUT_FILE) -> Dict:
    mined = mine_patterns()
    table = compose_strategy()
    validation = validate()

    candidate_id = "ALG_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    weight_sum = float(table.get("weight_sum", 0.0))
    delta_exp = float(validation.get("delta", {}).get("expectancy", 0.0))
    delta_pf = float(validation.get("delta", {}).get("profit_factor", 0.0))

    score = max(0.0, min(1.0, 0.5 + (delta_exp * 5.0) + (delta_pf * 0.2)))
    status = "pending_dennis" if validation.get("status") == "PASS" else "hold"

    queue = {
        "stamp": datetime.now().isoformat(),
        "pipeline": "PH7E_QUANT_FRAMEWORK",
        "candidate": {
            "candidate_id": candidate_id,
            "score": round(score, 6),
            "weight_sum": round(weight_sum, 6),
            "status": status,
            "engine_apply": "DISABLED",
            "mode": "shadow_only",
            "approval_gate": "pending_dennis",
        },
        "sources": {
            "mined_patterns": str(ROOT / "evidence" / "analysis" / "mined_patterns.json"),
            "shadow_strategy_table": str(TABLE_FILE),
            "strategy_validation_report": str(VALIDATION_FILE),
        },
        "summary": {
            "patterns": len(mined.get("patterns", [])),
            "weights": len(table.get("weights", [])),
            "validation_status": validation.get("status", "WARN"),
        },
    }
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(queue, indent=2), encoding="utf-8")
    return queue


if __name__ == "__main__":
    data = build_queue()
    print(str(OUT_FILE))
    print(f"status={data['candidate']['status']} score={data['candidate']['score']}")

