from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse, PlainTextResponse, JSONResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="NEXT-TRADE Ops Web")

BASE_DIR = Path(__file__).resolve().parent.parent
METRICS_FILE = BASE_DIR / "metrics" / "live_obs.jsonl"
LOG_DIR = BASE_DIR / "logs"

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

# --- Simple in-memory publish/subscribe broadcaster ---
SUBSCRIBERS: set[asyncio.Queue] = set()


def _latest_log_file() -> Optional[Path]:
    """Find latest log file (including rotated backups like live_obs_*.log.1, .log.2, etc.)"""
    if not LOG_DIR.exists():
        return None
    candidates = sorted(
        list(LOG_DIR.glob("live_obs_*")) + list(LOG_DIR.glob("live_obs_*.log*")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _tail_lines(path: Path, n: int = 50) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except Exception as exc:
        return f"[log-tail error] {exc}\n"


async def _publish(event: dict) -> None:
    """Fan-out event to all in-memory subscribers (non-blocking)."""
    dead = []
    for q in list(SUBSCRIBERS):
        try:
            q.put_nowait(event)
        except Exception:
            # If queue is unusable, mark for removal
            dead.append(q)
    for q in dead:
        try:
            SUBSCRIBERS.discard(q)
        except Exception:
            pass


async def _metrics_file_publisher() -> None:
    """Optional: simple background task to tail file and publish new lines.

    Not started automatically; kept for compatibility.
    """
    last_line = ""
    while True:
        try:
            if METRICS_FILE.exists():
                with METRICS_FILE.open("r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                if lines:
                    current = lines[-1].strip()
                    if current and current != last_line:
                        last_line = current
                        try:
                            payload = json.loads(current)
                        except Exception:
                            payload = {"raw": current}
                        await _publish(payload)
        except Exception:
            # ignore and continue
            pass
        await asyncio.sleep(2)


async def _sse_generator(q: asyncio.Queue) -> AsyncGenerator[str, None]:
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=15)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                # keepalive comment to prevent proxies from closing connection
                yield ": keepalive\n\n"
    finally:
        # cleanup handled by caller
        return


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse("index.html", {"request": request})


@app.get("/events")
async def events() -> StreamingResponse:
    """SSE endpoint backed by in-memory broadcaster."""
    q: asyncio.Queue = asyncio.Queue()
    SUBSCRIBERS.add(q)

    async def _stream():
        try:
            async for chunk in _sse_generator(q):
                yield chunk
        finally:
            try:
                SUBSCRIBERS.discard(q)
            except Exception:
                pass

    return StreamingResponse(_stream(), media_type="text/event-stream")


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await ws.accept()
    q: asyncio.Queue = asyncio.Queue()
    SUBSCRIBERS.add(q)
    try:
        while True:
            event = await q.get()
            try:
                await ws.send_text(json.dumps(event, ensure_ascii=False))
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        try:
            SUBSCRIBERS.discard(q)
        except Exception:
            pass


@app.post("/api/ops/test-event")
async def test_event(request: Request) -> JSONResponse:
    """Trigger endpoint for creating and broadcasting a test event."""
    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = {"value": body}
    except Exception:
        body = {}

    body.setdefault("ts", datetime.utcnow().isoformat() + "Z")
    body.setdefault("trace_id", str(uuid.uuid4()))
    body.setdefault("type", "test-event")

    # Append to metrics file for compatibility (best-effort)
    try:
        METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with METRICS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(body, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # Publish to in-memory subscribers
    try:
        await _publish(body)
    except Exception:
        pass

    return JSONResponse({"status": "ok", "event": body})


@app.get("/log-tail")
async def log_tail(lines: int = 50) -> PlainTextResponse:
    log_path = _latest_log_file()
    if not log_path:
        return PlainTextResponse("[no log file found]\n", status_code=404)
    return PlainTextResponse(_tail_lines(log_path, n=max(1, min(lines, 500))))


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
