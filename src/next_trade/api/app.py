from __future__ import annotations

import asyncio
import json
import os
from typing import Set

import requests
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
    return BinanceTestnetAdapter(
        api_key=os.getenv("BINANCE_TESTNET_API_KEY"),
        api_secret=os.getenv("BINANCE_TESTNET_API_SECRET"),
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
    api_key = os.getenv("BINANCE_TESTNET_API_KEY", "")
    headers = {"X-MBX-APIKEY": api_key}
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
