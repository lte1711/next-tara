from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/dev", tags=["dev-v1"])

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


def _to_ws_envelope(
    event_type: str, trace_id: str, ts_ms: int, severity: str, data: dict
):
    return {
        "type": event_type,
        "event_type": event_type,
        "ts": ts_ms,
        "trace_id": trace_id,
        "severity": severity,
        "data": data,
        "contract_version": CONTRACT_VERSION,
    }


async def _broadcast(request: Request, payload: dict) -> None:
    connections = getattr(request.app.state, "connections", None)
    if not isinstance(connections, set) or not connections:
        return

    dead = []
    for conn in list(connections):
        try:
            await conn.send_json(payload)
        except Exception:
            dead.append(conn)

    for conn in dead:
        connections.discard(conn)


@router.post("/emit-event")
async def emit_dev_event_v1(payload: dict, request: Request):
    project_root = _project_root()
    events_file = (
        project_root / "evidence" / "phase-s5-watchdog" / "watchdog_events.jsonl"
    )

    event_type = str(payload.get("event_type") or "DEV_EVENT")
    trace_id = str(payload.get("trace_id") or f"dev-{payload.get('index', '0')}")
    severity = str(payload.get("severity") or "INFO").upper()
    ts_ms = _to_epoch_ms(payload.get("ts"))
    ts_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()

    runtime_event = {
        "ts": ts_iso,
        "level": severity,
        "action": event_type,
        "trace_id": trace_id,
        "reason": "DEV_EMIT_EVENT",
    }

    data = {
        "index": payload.get("index"),
        "total": payload.get("total"),
        "source": "dev_emit",
        "metadata": payload.get("metadata", {}),
    }

    ws_event = _to_ws_envelope(
        event_type=event_type,
        trace_id=trace_id,
        ts_ms=ts_ms,
        severity=severity,
        data=data,
    )

    try:
        events_file.parent.mkdir(parents=True, exist_ok=True)
        with events_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(runtime_event, ensure_ascii=False) + "\n")
    except Exception:
        pass

    await _broadcast(request, ws_event)

    return {
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "emitted": event_type,
        "trace_id": trace_id,
        "ts": ts_ms,
    }
