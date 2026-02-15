from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

from next_trade.core.logging import get_logger

logger = get_logger(__name__)


# Fallback-safe imports for runtime helpers
try:
    from next_trade.runtime.run_context import get_run_id, append_jsonl
except Exception:  # pragma: no cover - fallbacks for editors/tests
    def get_run_id() -> Optional[str]:
        return None

    def append_jsonl(path: str, obj: Dict[str, Any]) -> None:  # pragma: no cover
        return

try:
    from next_trade.runtime.run_artifacts import get_paths_for_run, ensure_metrics, write_metrics
except Exception:  # pragma: no cover
    def get_paths_for_run(run_id: str):
        return {"events": None}

    ensure_metrics = None  # type: ignore
    write_metrics = None  # type: ignore


@dataclass
class KillSwitchState:
    is_active: bool = False
    activated_at: Optional[float] = None
    reason: Optional[str] = None
    risk_type: Optional[str] = None

    activation_recorded: bool = False
    recovery_recorded: bool = False


class KillSwitch:
    def __init__(self) -> None:
        self.state = KillSwitchState()

    def activate(self, reason: str, risk_type: str) -> bool:
        if self.state.is_active:
            return False
        now = time.time()
        self.state.is_active = True
        self.state.activated_at = now
        self.state.reason = reason
        self.state.risk_type = risk_type
        self.state.activation_recorded = False
        self.state.recovery_recorded = False
        return True

    def reset(self) -> None:
        self.state = KillSwitchState()


class Guardrail:
    def __init__(self, *, cooldown_s: float = 10.0, stability_window_n: int = 5) -> None:
        self.cooldown_s = float(cooldown_s)
        self.stability_window_n = int(stability_window_n)
        self.kill_switch = KillSwitch()

    def evaluate(self, *, reason: str = "", risk_type: str = "TEST_SIM") -> bool:
        # Minimal: activate always when called with reason/risk_type (caller controls)
        return self.kill_switch.activate(reason=reason, risk_type=risk_type)

    # --- API compatibility layer for smoke/legacy callers ---
    def on_kill_switch_trigger(self, *, reason: str, risk_type: str) -> bool:
        return self.kill_switch.activate(reason=reason, risk_type=risk_type)

    def is_kill_switch_on(self) -> bool:
        return bool(self.kill_switch.state.is_active)

    def get_kill_switch_state(self):
        return self.kill_switch.state

    def maybe_recover(self, *, latency_tracker=None, threshold_ms=None) -> bool:
        # Compatibility signature for smoke: accepts optional latency tracker
        if not self.kill_switch.state.is_active:
            return False

        now = time.time()

        # 1) cooldown gate
        if (now - (self.kill_switch.state.activated_at or 0.0)) < float(self.cooldown_s):
            return False

        # 2) latency gate (optional)
        if latency_tracker is not None and threshold_ms is not None:
            try:
                recent = latency_tracker.get_recent(self.stability_window_n)
                if not recent:
                    return False
                if any(x > threshold_ms for x in recent):
                    return False
            except Exception:
                return False

        # record recovery event and metrics best-effort
        try:
            run_id = get_run_id()
            if run_id is not None:
                paths = get_paths_for_run(run_id)
                if paths and paths.get("events") is not None:
                    append_jsonl(paths["events"], {
                        "event": "P1-011_kill_switch_recovered",
                        "recovered_at": int(time.time()),
                        "reason": self.kill_switch.state.reason,
                        "risk_type": self.kill_switch.state.risk_type,
                    })
                try:
                    m = ensure_metrics(run_id)
                    m["recovery_count"] = int(m.get("recovery_count", 0)) + 1
                    write_metrics(run_id, m)
                except Exception:
                    pass
        except Exception:
            pass

        self.kill_switch.reset()
        return True


_GLOBAL_GUARD: Guardrail | None = None

def get_global_guard() -> Guardrail:
    global _GLOBAL_GUARD
    if _GLOBAL_GUARD is None:
        _GLOBAL_GUARD = Guardrail()
    return _GLOBAL_GUARD
