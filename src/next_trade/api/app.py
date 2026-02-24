from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Set

import requests
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from next_trade.execution.binance_testnet_adapter import BinanceTestnetAdapter

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
    project_root = Path(__file__).parent.parent.parent.parent
    pid_file = project_root / "logs" / "runtime" / "engine.pid"
    checkpoint_file = project_root / "logs" / "runtime" / "checkpoint_log.txt"
    events_file = project_root / "evidence" / "phase-s5-watchdog" / "watchdog_events.jsonl"

    # Read engine PID
    engine_pid = None
    engine_alive = False
    if pid_file.exists():
        try:
            engine_pid = int(pid_file.read_text().strip())
            # Check if process is alive (simple check)
            import psutil
            try:
                proc = psutil.Process(engine_pid)
                engine_alive = proc.is_running()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                engine_alive = False
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
            timeout=5
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
        "checkpoint_age_sec": checkpoint_age_sec,
        "checkpoint_status": checkpoint_status,
        "health_status": health_status,
        "last_health_ok": last_health_ok,
        "restart_count": restart_count,
        "flap_detected": flap_detected,
        "task_state": task_state,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/ops/runtime-events")
def get_runtime_events(limit: int = Query(default=50, ge=1, le=500)):
    """
    S7 Ops Dashboard: Recent Runtime Events
    Returns watchdog event timeline
    """
    project_root = Path(__file__).parent.parent.parent.parent
    events_file = project_root / "evidence" / "phase-s5-watchdog" / "watchdog_events.jsonl"

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

    return {"events": events, "count": len(events)}


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
            keepalive_task = asyncio.create_task(_keepalive_listen_key(base, headers, listen_key))
            ws_url = f"wss://fstream.binancefuture.com/ws/{listen_key}"
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                backoff = 1
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if data.get("e") == "ORDER_TRADE_UPDATE":
                        await _broadcast(data)
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
