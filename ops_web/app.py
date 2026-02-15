
from __future__ import annotations

import asyncio
import json
import uuid
import contextlib
import time
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional, Set

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse, PlainTextResponse, JSONResponse
from fastapi.templating import Jinja2Templates


# --- Broadcast bus (safe subscribe/unsubscribe/shutdown) ---


class BroadcastBus:
    def __init__(self, queue_maxsize: int = 200):
        self._subs: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        self._closed = False
        self._queue_maxsize = queue_maxsize
        # backpressure metrics
        self._drop_count = 0
        self._last_drop_ts = 0.0

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._queue_maxsize)
        async with self._lock:
            if self._closed:
                # already closed: push sentinel and return
                try:
                    q.put_nowait(None)
                except Exception:
                    pass
                return q
            self._subs.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            if q in self._subs:
                self._subs.remove(q)
        try:
            q.put_nowait(None)
        except Exception:
            pass

    async def publish(self, event: Dict[str, Any]) -> None:
        async with self._lock:
            if self._closed:
                return
            subs = list(self._subs)

        for q in subs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # backpressure: count and sample-log (do not spam)
                try:
                    self._drop_count += 1
                    now = time.time()
                    if now - self._last_drop_ts > 5:
                        self._last_drop_ts = now
                        # use logger; fall back to print
                        try:
                            logging.getLogger("ops_web").warning(
                                f"Backpressure drop occurred. total_drop={self._drop_count}"
                            )
                        except Exception:
                            print(f"[WARN] Backpressure drop occurred. total_drop={self._drop_count}")
                        # append a sampled backpressure event to metrics file for observability
                        try:
                            mf = Path(__file__).resolve().parent.parent / "metrics" / "live_obs.jsonl"
                            mf.parent.mkdir(parents=True, exist_ok=True)
                            with mf.open("a", encoding="utf-8") as mfh:
                                bp = {
                                    "ts": datetime.utcnow().isoformat() + "Z",
                                    "type": "backpressure-drop",
                                    "drop_count": self._drop_count,
                                }
                                mfh.write(json.dumps(bp, ensure_ascii=False) + "\n")
                        except Exception:
                            pass
                except Exception:
                    pass
                continue
            except Exception:
                continue

    async def shutdown(self) -> None:
        async with self._lock:
            self._closed = True
            subs = list(self._subs)
            self._subs.clear()

        for q in subs:
            try:
                q.put_nowait(None)
            except Exception:
                pass


bus = BroadcastBus()

_file_publisher_task: Optional[asyncio.Task] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _file_publisher_task
    # startup: start optional metrics file tailer task
    try:
        _file_publisher_task = asyncio.create_task(_metrics_file_publisher())
    except Exception:
        _file_publisher_task = None
    try:
        yield
    finally:
        # cancel background task
        try:
            if _file_publisher_task:
                _file_publisher_task.cancel()
                with contextlib.suppress(Exception):
                    await _file_publisher_task
        except Exception:
            pass
        # shutdown bus to wake subscribers
        try:
            await bus.shutdown()
        except Exception:
            pass


app = FastAPI(lifespan=lifespan, title="NEXT-TRADE Ops Web")

BASE_DIR = Path(__file__).resolve().parent.parent
METRICS_FILE = BASE_DIR / "metrics" / "live_obs.jsonl"
LOG_DIR = BASE_DIR / "logs"

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


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
    """Compatibility wrapper: publish via bus."""
    try:
        await bus.publish(event)
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
                        await bus.publish(payload)
        except Exception:
            # ignore and continue
            pass
        await asyncio.sleep(2)


# (SSE generator inlined into /events handler to guarantee unsubscribe in finally)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse("index.html", {"request": request})


@app.get("/events")
async def events() -> StreamingResponse:
    """SSE endpoint using BroadcastBus.subscribe/unsubscribe."""
    q: asyncio.Queue = await bus.subscribe()

    async def _stream():
        try:
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if item is None:
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        finally:
            try:
                await bus.unsubscribe(q)
            except Exception:
                pass

    return StreamingResponse(_stream(), media_type="text/event-stream")


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await ws.accept()
    q: asyncio.Queue = await bus.subscribe()
    try:
        while True:
            item = await q.get()
            if item is None:
                break
            try:
                await ws.send_text(json.dumps(item, ensure_ascii=False))
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await bus.unsubscribe(q)
        except Exception:
            pass
        try:
            await ws.close()
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
        await bus.publish(body)
    except Exception:
        pass

    return JSONResponse({"status": "ok", "event": body})


@app.get("/api/ops/metrics")
async def ops_metrics() -> JSONResponse:
    """Expose simple operational metrics for the broadcast bus."""
    try:
        drop = int(getattr(bus, "_drop_count", 0))
        subs = 0
        try:
            # best-effort subscriber count
            subs = len(getattr(bus, "_subs", []))
        except Exception:
            subs = 0
        return JSONResponse({"drop_count": drop, "subscribers": subs})
    except Exception:
        return JSONResponse({"error": "metrics unavailable"}, status_code=500)


@app.get("/log-tail")
async def log_tail(lines: int = 50) -> PlainTextResponse:
    log_path = _latest_log_file()
    if not log_path:
        return PlainTextResponse("[no log file found]\n", status_code=404)
    return PlainTextResponse(_tail_lines(log_path, n=max(1, min(lines, 500))))


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
