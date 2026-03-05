from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

ROOT = Path(r"C:\projects\NEXT-TRADE")
ANALYSIS = ROOT / "evidence" / "analysis"
OUT_TXT = ANALYSIS / "ph7e_daily_health.txt"
OUT_JSON = ANALYSIS / "ph7e_daily_health.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_health() -> Dict:
    required = {
        "mined_patterns": ANALYSIS / "mined_patterns.json",
        "mined_patterns_v2": ANALYSIS / "mined_patterns_v2.json",
        "shadow_strategy_table": ANALYSIS / "shadow_strategy_table.json",
        "strategy_validation_report": ANALYSIS / "strategy_validation_report.json",
        "implant_queue": ANALYSIS / "implant_queue.json",
    }
    files_ok = all(p.exists() for p in required.values())
    missing = [k for k, p in required.items() if not p.exists()]

    validation = _load_json(required["strategy_validation_report"])
    table = _load_json(required["shadow_strategy_table"])
    queue = _load_json(required["implant_queue"])

    validation_status = str(validation.get("status", "MISSING")).upper()
    weight_sum = float(table.get("weight_sum", 0.0) or 0.0)
    apply_status = str(queue.get("candidate", {}).get("engine_apply", "UNKNOWN")).upper()

    checks = {
        "output_files_exist": files_ok,
        "validation_pass": validation_status == "PASS",
        "weight_sum_cap": weight_sum <= 0.50,
        "constitution_apply_disabled": apply_status == "DISABLED",
    }
    ok = all(checks.values())
    status = "PASS" if ok else "FAIL"

    payload = {
        "version": "v1",
        "stamp": datetime.now().isoformat(),
        "status": status,
        "checks": checks,
        "values": {
            "validation_status": validation_status,
            "weight_sum": round(weight_sum, 6),
            "engine_apply_status": apply_status,
        },
        "missing": missing,
        "sources": {k: str(v) for k, v in required.items()},
    }
    return payload


def write_health(payload: Dict) -> None:
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines: List[str] = []
    lines.append(f"STAMP={payload['stamp']}")
    lines.append(f"STATUS={payload['status']}")
    lines.append(f"OUTPUT_FILES_EXIST={payload['checks']['output_files_exist']}")
    lines.append(f"VALIDATION_PASS={payload['checks']['validation_pass']}")
    lines.append(f"WEIGHT_SUM_CAP={payload['checks']['weight_sum_cap']}")
    lines.append(
        f"CONSTITUTION_APPLY_DISABLED={payload['checks']['constitution_apply_disabled']}"
    )
    lines.append(f"VALIDATION_STATUS={payload['values']['validation_status']}")
    lines.append(f"WEIGHT_SUM={payload['values']['weight_sum']}")
    lines.append(f"ENGINE_APPLY_STATUS={payload['values']['engine_apply_status']}")
    lines.append(f"MISSING={','.join(payload['missing']) if payload['missing'] else '-'}")
    OUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    p = build_health()
    write_health(p)
    print(str(OUT_TXT))
    print(f"status={p['status']}")

