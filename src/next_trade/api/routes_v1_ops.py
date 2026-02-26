from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/v1/ops", tags=["ops-v1"])

CONTRACT_VERSION = "v1"


def _project_root() -> Path:
    return Path(__file__).parent.parent.parent.parent


def _to_epoch_ms(value) -> int:
    if isinstance(value, (int, float)):
        value_int = int(value)
        return value_int if value_int > 10_000_000_000 else value_int * 1000
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except Exception:
            return int(datetime.now(timezone.utc).timestamp() * 1000)
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _runtime_health_snapshot() -> dict:
    project_root = _project_root()
    pid_file = project_root / "logs" / "runtime" / "engine.pid"
    checkpoint_file = project_root / "logs" / "runtime" / "checkpoint_log.txt"
    events_file = (
        project_root / "evidence" / "phase-s5-watchdog" / "watchdog_events.jsonl"
    )

    engine_pid = None
    engine_alive = False
    engine_cmdline_hint = None
    if pid_file.exists():
        try:
            engine_pid = int(pid_file.read_text().strip())
            import psutil

            def pid_alive(pid: int) -> bool:
                if not pid or pid <= 0:
                    return False
                try:
                    return psutil.pid_exists(pid)
                except Exception:
                    return False

            def cmdline_hint(pid: int) -> str | None:
                try:
                    proc = psutil.Process(pid)
                    cmd = " ".join(proc.cmdline() or [])
                    return cmd[:300] if cmd else None
                except psutil.AccessDenied:
                    return "ACCESS_DENIED"
                except psutil.NoSuchProcess:
                    return None
                except Exception:
                    return None

            engine_alive = pid_alive(engine_pid)
            engine_cmdline_hint = cmdline_hint(engine_pid)
        except Exception:
            pass

    checkpoint_age_sec = None
    checkpoint_status = "UNKNOWN"
    if checkpoint_file.exists():
        try:
            mtime = checkpoint_file.stat().st_mtime
            age = datetime.now().timestamp() - mtime
            checkpoint_age_sec = round(age, 1)
            if age < 15:
                checkpoint_status = "FRESH"
            elif age < 60:
                checkpoint_status = "STALE"
            else:
                checkpoint_status = "EXPIRED"
        except Exception:
            pass

    last_health_ok = None
    restart_count = 0
    flap_detected = False
    if events_file.exists():
        try:
            lines = events_file.read_text(encoding="utf-8").strip().split("\n")
            for line in reversed(lines[-50:]):
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get("action") == "HEALTH_OK" and last_health_ok is None:
                    last_health_ok = event.get("ts")
                if event.get("action") in ["ENGINE_START", "RESTART"]:
                    restart_count += 1
                if event.get("action") == "FLAP_DETECTED":
                    flap_detected = True
        except Exception:
            pass

    if engine_alive and checkpoint_status == "FRESH":
        health_status = "OK"
    elif engine_alive and checkpoint_status in ["STALE", "UNKNOWN"]:
        health_status = "WARN"
    else:
        health_status = "CRITICAL"

    task_state = "UNKNOWN"
    try:
        import subprocess

        result = subprocess.run(
            ["schtasks", "/Query", "/TN", "NEXTTRADE_WATCHDOG", "/FO", "LIST"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "Status:" in line:
                    state = line.split(":")[-1].strip()
                    if "Running" in state:
                        task_state = "Running"
                    elif "Ready" in state:
                        task_state = "Ready"
                    else:
                        task_state = state
                    break
    except Exception:
        pass

    return {
        "engine_pid": engine_pid,
        "engine_alive": engine_alive,
        "engine_cmdline_hint": engine_cmdline_hint,
        "checkpoint_age_sec": checkpoint_age_sec,
        "checkpoint_status": checkpoint_status,
        "health_status": health_status,
        "last_health_ok": last_health_ok,
        "restart_count": restart_count,
        "flap_detected": flap_detected,
        "task_state": task_state,
    }


def _runtime_events(limit: int) -> list[dict]:
    project_root = _project_root()
    events_file = (
        project_root / "evidence" / "phase-s5-watchdog" / "watchdog_events.jsonl"
    )
    live_obs_file = project_root / "metrics" / "live_obs.jsonl"

    events: list[dict] = []
    if events_file.exists():
        try:
            lines = events_file.read_text(encoding="utf-8").strip().split("\n")
            for line in reversed(lines[-limit:]):
                if line.strip():
                    events.append(json.loads(line))
        except Exception:
            pass

    if live_obs_file.exists():
        try:
            lines = live_obs_file.read_text(encoding="utf-8").strip().split("\n")
            for line in reversed(lines[-limit:]):
                if not line.strip():
                    continue
                raw = json.loads(line)
                events.append(
                    {
                        "ts": (
                            raw.get("ts")
                            if raw.get("ts")
                            else datetime.now(timezone.utc).isoformat()
                        ),
                        "level": raw.get("risk_level", "INFO"),
                        "action": raw.get("type", "LIVE_OBS"),
                        "reason": raw.get("reason"),
                        "trace_id": raw.get("trace_id"),
                        "data": raw,
                    }
                )
        except Exception:
            pass

    return sorted(
        events, key=lambda event: _to_epoch_ms(event.get("ts")), reverse=True
    )[:limit]


@router.get("/health")
def get_ops_health_v1():
    snapshot = _runtime_health_snapshot()
    return {
        "contract_version": CONTRACT_VERSION,
        "ts": datetime.now(timezone.utc).isoformat(),
        "status": snapshot.get("health_status", "UNKNOWN"),
        "data": snapshot,
    }


@router.get("/state")
def get_ops_state_v1():
    health = _runtime_health_snapshot()
    checkpoint_status = str(health.get("checkpoint_status") or "UNKNOWN")
    task_state = str(health.get("task_state") or "UNKNOWN")
    engine_alive = bool(health.get("engine_alive"))
    restart_count = int(health.get("restart_count") or 0)
    checkpoint_age_sec = float(health.get("checkpoint_age_sec") or 0)
    is_critical = str(health.get("health_status") or "").upper() == "CRITICAL"

    pending_total = 0
    if not engine_alive:
        pending_total += 1
    if bool(health.get("flap_detected")):
        pending_total += 1

    return {
        "contract_version": CONTRACT_VERSION,
        "ts": datetime.now(timezone.utc).isoformat(),
        "engine": {
            "pid": health.get("engine_pid"),
            "alive": engine_alive,
            "cmdline_hint": health.get("engine_cmdline_hint"),
            "task_state": task_state,
            "health_status": health.get("health_status"),
        },
        "kill": {
            "is_on": is_critical,
            "reason": task_state,
        },
        "counters": {
            "published": restart_count,
            "consumed": 1 if engine_alive else 0,
            "pending_total": pending_total,
            "restart_count": restart_count,
        },
        "freshness": {
            "checkpoint_age_sec": checkpoint_age_sec,
            "checkpoint_status": checkpoint_status,
            "is_stale": checkpoint_status in ["STALE", "EXPIRED", "UNKNOWN"],
            "last_health_ok": health.get("last_health_ok"),
            "flap_detected": bool(health.get("flap_detected")),
        },
    }


@router.get("/positions")
def get_ops_positions_v1():
    return {
        "contract_version": CONTRACT_VERSION,
        "ts": int(datetime.now(timezone.utc).timestamp()),
        "positions": [],
    }


@router.get("/risks")
def get_ops_risks_v1(limit: int = Query(default=20, ge=1, le=500)):
    runtime_events = _runtime_events(limit)
    items = []
    for index, event in enumerate(runtime_events):
        level = str(event.get("level") or "INFO")
        event_type = str(event.get("action") or event.get("event_type") or "UNKNOWN")
        ts_ms = _to_epoch_ms(event.get("ts"))
        trace_id = str(event.get("trace_id") or f"risk-{index}")
        reason = str(event.get("reason") or event_type)
        items.append(
            {
                "timestamp": ts_ms,
                "event_id": f"{trace_id}-{index}",
                "event_type": event_type,
                "severity": level,
                "reason": reason,
                "trace_id": trace_id,
                "data": (
                    event.get("data") if isinstance(event.get("data"), dict) else {}
                ),
            }
        )

    return {
        "contract_version": CONTRACT_VERSION,
        "count": len(items),
        "items": items,
    }
