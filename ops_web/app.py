

from __future__ import annotations

import os
import asyncio
import uuid
import time
from contextlib import suppress
# --- Broadcast bus (safe subscribe/unsubscribe/shutdown) ---

# --- DEV/LOCAL Heartbeat Publisher (OPS_EMIT_HEARTBEAT=1) ---
async def _ops_heartbeat_loop(event_bus, interval_sec: float = 1.0):
    """
    DEV/LOCAL fallback heartbeat publisher.
    Emits ws_heartbeat periodically so OPS dashboard can show LIVE
    even when Evergreen Runner entrypoint is absent.
    """
    seq = 0
    try:
        while True:
            seq += 1
            evt = {
                "type": "ws_heartbeat",
                "ts": time.time(),
                "level": "info",
                "source": "ops_web",
                "message": "ops heartbeat",
                "data": {
                    "seq": seq,
                },
            }
            await event_bus.publish(evt)

            # Also emit a guardrail_update event (dev/local) so UI can update RISK/KILL
            try:
                guard_fn = globals().get("_build_guardrail_update")
                if callable(guard_fn):
                    guard = guard_fn()
                else:
                    # Fallback (never crash on NameError / partial init)
                    guard = {
                        "type": "guardrail_update",
                        "ts": int(time.time() * 1000),
                        "trace_id": "no-trace",
                        "source": "guardrail",
                        "severity": "info",
                        "data": {
                            "risk_level": "OK",
                            "kill_switch": False,
                            "downgrade_level": 0,
                            "reason": "guard_fn_missing",
                            "recovery_count": 0,
                        },
                    }
                await event_bus.publish(guard)
            except Exception:
                # best-effort: do not break heartbeat loop
                pass
            await asyncio.sleep(interval_sec)
    except asyncio.CancelledError:
        return
import json
import uuid
import contextlib
import time
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional, Set

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Header, HTTPException
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
    PlainTextResponse,
    JSONResponse,
    FileResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware


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

def _new_trace_id() -> str:
    return uuid.uuid4().hex


import os

# queue maxsize can be controlled via OPS_BUS_QMAX env var for testing
try:
    _qmax = int(os.environ.get("OPS_BUS_QMAX", "200"))
except Exception:
    _qmax = 200
bus = BroadcastBus(queue_maxsize=_qmax)

# For testing: keep references to intentionally-hung subscribers (do not consume)
HUNG_SUBS: list[asyncio.Queue] = []

_file_publisher_task: Optional[asyncio.Task] = None
_ops_hb_task: Optional[asyncio.Task] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _file_publisher_task, _ops_hb_task
    # startup: start optional metrics file tailer task
    try:
        _file_publisher_task = asyncio.create_task(_metrics_file_publisher())
    except Exception:
        _file_publisher_task = None

    # DEV/LOCAL Heartbeat Publisher (OPS_EMIT_HEARTBEAT=1)
    emit = os.getenv("OPS_EMIT_HEARTBEAT", "0") == "1"
    interval = float(os.getenv("OPS_HEARTBEAT_SEC", "1.0"))
    if emit:
        _ops_hb_task = asyncio.create_task(_ops_heartbeat_loop(bus, interval), name="ops_heartbeat")
    else:
        _ops_hb_task = None

    try:
        yield
    finally:
        # cancel background tasks
        try:
            if _file_publisher_task:
                _file_publisher_task.cancel()
                with suppress(asyncio.CancelledError):
                    await _file_publisher_task
        except Exception:
            pass
        try:
            if _ops_hb_task:
                _ops_hb_task.cancel()
                with suppress(asyncio.CancelledError):
                    await _ops_hb_task
        except Exception:
            pass
        # shutdown bus to wake subscribers
        try:
            await bus.shutdown()
        except Exception:
            pass


app = FastAPI(lifespan=lifespan, title="NEXT-TRADE Ops Web")

# CORS 설정: 로컬 Next.js 개발 서버 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3001",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# static files for ops dashboard
STATIC_DIR = Path(__file__).resolve().parent / "static"
try:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/ops")
async def ops_dashboard():
    p = STATIC_DIR / "ops_dashboard.html"
    if p.exists():
        return FileResponse(str(p))
    return RedirectResponse(url="/")

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
    try:
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
                            # Also emit guardrail_update each time metrics are published
                            try:
                                guard = _build_guardrail_update()
                                await bus.publish(guard)
                            except Exception:
                                pass
            except Exception:
                # ignore and continue
                pass
            await asyncio.sleep(2)
    except asyncio.CancelledError:
        return


# (SSE generator inlined into /events handler to guarantee unsubscribe in finally)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse("index.html", {"request": request})


@app.get("/events")
async def events() -> StreamingResponse:
    """SSE endpoint using BroadcastBus.subscribe/unsubscribe."""
    q: asyncio.Queue = await bus.subscribe()


    log = logging.getLogger("ops_web")
    trace_id = _new_trace_id()

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


@app.websocket("/api/ws/events")
async def ws_events(ws: WebSocket):
    await ws.accept()
    q: asyncio.Queue = await bus.subscribe()

    log = logging.getLogger("ops_web")
    trace_id = _new_trace_id()

    try:
        while True:
            item = await q.get()
            if item is None:
                break

            try:
                # 1) item 송신 (trace_id/ts audit-native)
                if isinstance(item, dict):
                    item.setdefault("trace_id", trace_id)
                    item.setdefault("ts", datetime.utcnow().isoformat() + "Z")
                await ws.send_text(json.dumps(item, ensure_ascii=False))

                # 2) guardrail_update 송신 (trace_id/ts audit-native)
                guard = _build_guardrail_update()
                if isinstance(guard, dict):
                    guard.setdefault("trace_id", trace_id)
                    guard.setdefault("ts", datetime.utcnow().isoformat() + "Z")

                log.info("guardrail_update built trace_id=%s", trace_id)
                await ws.send_text(json.dumps(guard, ensure_ascii=False))
                log.info("guardrail_update sent trace_id=%s", trace_id)

            except Exception:
                log.exception("guardrail_update send error trace_id=%s", trace_id)
                break

    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        return
    finally:
        with suppress(Exception):
            await bus.unsubscribe(q)
        with suppress(Exception):
            await ws.close()

@app.post("/api/ops/test-event")
async def test_event(request: Request) -> JSONResponse:
    """Trigger endpoint for creating and broadcasting a test event."""
    try:
        body = await request.json()
        trace_id = body.get("trace_id") if isinstance(body, dict) else None
        if not trace_id:
            trace_id = _new_trace_id()

        if not isinstance(body, dict):
            body = {"value": body}
    except Exception:
        body = {}

    body.setdefault("ts", datetime.utcnow().isoformat() + "Z")
    body.setdefault("trace_id", trace_id)
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
    """Expose operational metrics for the broadcast bus + live_obs state."""
    try:
        drop = int(getattr(bus, "_drop_count", 0))
        subs = 0
        try:
            subs = len(getattr(bus, "_subs", []))
        except Exception:
            subs = 0
        
        base = {"drop_count": drop, "subscribers": subs}
        
        # Extend with live_obs data (if available)
        obs = _read_last_obs(METRICS_FILE)
        if not obs:
            return JSONResponse(base)
        
        now_ms = int(time.time() * 1000)
        ts_ms = _normalize_ts_ms(obs.get("ts"))
        if ts_ms is None:
            return JSONResponse(base)
        
        age_sec = max(0.0, (now_ms - ts_ms) / 1000.0)
        
        base.update({
            "last_obs_ts_ms": ts_ms,
            "last_obs_age_sec": round(age_sec, 3),
            "ws_messages_total": obs.get("ws_messages_total"),
            "event_published": obs.get("event_published"),
            "event_consumed": obs.get("event_consumed"),
            "event_queue_depth": obs.get("event_queue_depth"),
            "event_queue_depth_max_seen": obs.get("event_queue_depth_max_seen"),
        })
        return JSONResponse(base)
    except Exception:
        return JSONResponse({"error": "metrics unavailable"}, status_code=500)


def _read_last_obs(metrics_file: Path, max_tail_lines: int = 200) -> Optional[dict]:
    """Read the last valid JSON object with metrics fields from live_obs.jsonl"""
    if not metrics_file or not metrics_file.exists():
        return None
    try:
        text = metrics_file.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        tail = lines[-max_tail_lines:] if len(lines) > max_tail_lines else lines
        for ln in reversed(tail):
            ln = ln.strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
                if isinstance(obj, dict) and "ws_messages_total" in obj:
                    # This is an MVP producer line (has ws_messages_total field)
                    return obj
            except Exception:
                continue
    except Exception:
        pass
    return None

# === MVP Metrics Producer (ops_web embedded) ==========================
OPS_MVP_PRODUCER = os.getenv("OPS_MVP_PRODUCER", "0") == "1"
OPS_MVP_INTERVAL_SEC = float(os.getenv("OPS_MVP_INTERVAL_SEC", "1.0"))
OPS_MVP_STALE_SEC = float(os.getenv("OPS_MVP_STALE_SEC", "2.0"))

_mvp_task = None  # asyncio.Task | None

def _read_last_obs(metrics_file, max_tail_lines: int = 200):
    """
    Read the most recent valid metrics JSON line from live_obs.jsonl.

    Priority:
    1) Lines containing 'ws_messages_total' (MVP producer / real runtime metrics)
    2) Fallback: any dict containing 'ts'
    """

    if not metrics_file or not metrics_file.exists():
        return None

    try:
        text = metrics_file.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        if not lines:
            return None

        tail = lines[-max_tail_lines:] if len(lines) > max_tail_lines else lines

        fallback = None

        for ln in reversed(tail):
            ln = ln.strip()
            if not ln:
                continue

            try:
                obj = json.loads(ln)

                if not isinstance(obj, dict):
                    continue

                # 1️⃣ MVP / Runtime metrics line (preferred)
                if "ws_messages_total" in obj:
                    return obj

                # 2️⃣ fallback candidate
                if "ts" in obj and fallback is None:
                    fallback = obj

            except Exception:
                continue

        return fallback

    except Exception:
        return None


def _rollover_if_dirty_live_obs(path: Path):
    """
    If existing live_obs.jsonl tail doesn't contain MVP metric keys, roll it over.
    Keeps legacy kill-switch lines from polluting the MVP stream.
    """
    if not path.exists():
        return
    try:
        tail = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-5:]
        ok = 0
        for ln in tail:
            try:
                obj = json.loads(ln)
                if isinstance(obj, dict) and ("ws_messages_total" in obj or "event_queue_depth" in obj):
                    ok += 1
            except Exception:
                continue
        if ok >= 1:
            return
    except Exception:
        pass

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_name(f"live_obs_{ts}.jsonl")
    try:
        path.rename(bak)
    except Exception:
        pass

async def _mvp_metrics_producer_loop():
    """
    Produce MVP metrics rows only when file is stale (no external producer).
    """
    _rollover_if_dirty_live_obs(METRICS_FILE)

    start = time.time()
    ticks = 0
    ws_messages_total = 0
    event_published = 0
    event_consumed = 0
    event_queue_depth_max = 0

    logger.info("[OPS_MVP_PRODUCER] enabled: writing -> %s", str(METRICS_FILE))

    while True:
        try:
            # If an external producer is already updating the file, stay passive.
            obs = _read_last_obs(METRICS_FILE)
            if obs is not None:
                ts_ms = _normalize_ts_ms(obs.get("ts"))
                if ts_ms is not None:
                    now_ms = int(time.time() * 1000)
                    age_sec = max(0.0, (now_ms - ts_ms) / 1000.0)
                    if age_sec < OPS_MVP_STALE_SEC:
                        await asyncio.sleep(OPS_MVP_INTERVAL_SEC)
                        continue

            now = time.time()
            ticks += 1

            # MVP counters
            ws_messages_total += 2
            event_published += 1
            event_consumed += 1

            event_queue_depth = max(0, event_published - event_consumed)
            event_queue_depth_max = max(event_queue_depth_max, event_queue_depth)

            row = {
                "ts": now,
                "elapsed_sec": round(now - start, 3),
                "ticks": ticks,
                "ws_messages_total": ws_messages_total,
                "event_published": event_published,
                "event_consumed": event_consumed,
                "event_queue_depth": event_queue_depth,
                "event_queue_depth_max_seen": event_queue_depth_max,
                "ledger_global_pnl": 0.0,
                "ledger_peak_pnl": 0.0,
                "ledger_worst_dd": 0.0,
            }

            METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with METRICS_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        except Exception:
            logger.exception("[OPS_MVP_PRODUCER] loop error")
        finally:
            await asyncio.sleep(OPS_MVP_INTERVAL_SEC)
# =====================================================================



def _normalize_ts_ms(ts_val) -> Optional[int]:
    """Convert ts to milliseconds. Handles sec (float), sec (int), or ms (int)."""
    try:
        if ts_val is None or ts_val == "":
            return None
        ts = float(ts_val)
        # Heuristic: seconds are ~1.7e9, ms are ~1.7e12
        if ts < 10_000_000_000:
            ts *= 1000.0
        return int(ts)
    except Exception:
        return None


def _get_risk_snapshot_payload() -> dict:
    """
    Single source of truth for guardrail snapshot payload.
    Must match /api/ops/risk-snapshot schema.
    Used by both HTTP endpoint and WS guardrail_update events.
    """
    defaults = {
        "ts": int(time.time() * 1000),
        "risk_level": "OK",
        "kill_switch": False,
        "downgrade_level": 0,
        "reason": "",
        "trace_id": "no-trace",
        "recovery_count": 0,
    }

    payload = defaults.copy()

    # Best-effort: try to read last metrics line for overrides (if any)
    try:
        if METRICS_FILE.exists():
            with METRICS_FILE.open("r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            if lines:
                try:
                    last = json.loads(lines[-1])
                    # allow last to override any keys if present and not None
                    for k in list(defaults.keys()):
                        if k in last and last[k] is not None:
                            payload[k] = last[k]
                except Exception:
                    # ignore malformed lines
                    pass
    except Exception:
        # ignore any IO errors and fall back to defaults
        pass

    # Ensure types and no None values
    try:
        payload["ts"] = int(payload.get("ts") or defaults["ts"])
    except Exception:
        payload["ts"] = defaults["ts"]

    payload["risk_level"] = str(payload.get("risk_level") or defaults["risk_level"])
    payload["kill_switch"] = bool(payload.get("kill_switch") is True)
    try:
        payload["downgrade_level"] = int(payload.get("downgrade_level") or 0)
    except Exception:
        payload["downgrade_level"] = 0
    payload["reason"] = str(payload.get("reason") or "")
    # Enforce non-empty trace_id per protocol: use "no-trace" when missing/empty
    payload["trace_id"] = str(payload.get("trace_id") or "no-trace")
    try:
        payload["recovery_count"] = int(payload.get("recovery_count") or 0)
    except Exception:
        payload["recovery_count"] = 0

    return payload


@app.get("/api/ops/health")
async def ops_health() -> JSONResponse:
    """Health check endpoint for ops dashboard."""
    return JSONResponse({"status": "ok", "ts": int(time.time() * 1000)})


@app.get("/api/ops/evergreen/status")
async def ops_evergreen_status() -> JSONResponse:
    """Evergreen status endpoint - returns mock data when runner not active."""
    return JSONResponse({
        "status": "OK",
        "uptime_sec": 0,
        "last_heartbeat_ts": int(time.time() * 1000),
        "mode": "DEV",
    })


@app.get("/api/ops/history")
async def ops_history(hours: int = 24) -> JSONResponse:
    """Historical events endpoint - returns empty array when no data."""
    return JSONResponse({"events": [], "hours": hours})


@app.get("/api/ops/alerts")
async def ops_alerts(limit: int = 50) -> JSONResponse:
    """Alerts endpoint - returns empty array when no active alerts."""
    return JSONResponse({"alerts": [], "limit": limit})


@app.get("/api/ops/logs/stdout")
async def ops_logs_stdout(limit: int = 200) -> JSONResponse:
    """Stdout logs endpoint - returns recent log lines."""
    return JSONResponse({"logs": [], "limit": limit})


@app.get("/api/ops/logs/stderr")
async def ops_logs_stderr(limit: int = 200) -> JSONResponse:
    """Stderr logs endpoint - returns recent error log lines."""
    return JSONResponse({"logs": [], "limit": limit})


@app.get("/api/state/engine")
async def state_engine() -> JSONResponse:
    """Engine state endpoint - returns default state when runner not active."""
    return JSONResponse({
        "running": False,
        "uptime_sec": 0,
        "processed_events": 0,
        "last_heartbeat_ts": None,
    })


@app.get("/api/state/positions")
async def state_positions() -> JSONResponse:
    """Positions state endpoint - returns empty when no active positions."""
    return JSONResponse({"positions": []})


@app.get("/api/history/risks")
async def history_risks(limit: int = 20) -> JSONResponse:
    """Risk history endpoint - returns empty when no risk events."""
    return JSONResponse({"risks": [], "limit": limit})


@app.get("/api/ops/risk-snapshot")
async def risk_snapshot() -> JSONResponse:
    """Return a small risk snapshot used by institutional UI.

    Must always return a JSON object with the fixed schema. Never return None
    or raise a 500. If internal guardrail data is unavailable, return defaults.
    """
    return JSONResponse(_get_risk_snapshot_payload())


@app.post("/api/ops/kill", response_model=None)
async def ops_kill(payload: dict, x_ops_token: str = Header(default="")):
    """Set kill switch on/off. Requires X-OPS-TOKEN header if configured."""
    expected = os.getenv("NEXT_TRADE_OPS_TOKEN") or ""
    if expected:
        if not x_ops_token or x_ops_token != expected:
            raise HTTPException(status_code=403, detail="Invalid OPS token")

    try:
        kill = bool(payload.get("kill") is True)
        reason = str(payload.get("reason") or "")
    except Exception:
        raise HTTPException(status_code=400, detail="invalid payload")

    # build updated snapshot based on current snapshot
    snap = _get_risk_snapshot_payload()
    snap["kill_switch"] = kill
    snap["risk_level"] = "CRITICAL" if kill else "OK"
    snap["downgrade_level"] = 2 if kill else 0
    snap["reason"] = reason
    snap["ts"] = int(time.time() * 1000)
    snap["trace_id"] = str(uuid.uuid4())

    # append snapshot to metrics file (best-effort)
    try:
        METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with METRICS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(snap, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # audit log
    try:
        audit = {
            "ts": int(time.time() * 1000),
            "trace_id": snap["trace_id"],
            "action": "kill_on" if kill else "kill_off",
            "reason": reason,
            "actor_ip": None,
        }
        audit_path = METRICS_FILE.parent / "kill_audit.jsonl"
        with audit_path.open("a", encoding="utf-8") as af:
            af.write(json.dumps(audit, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # broadcast guardrail_update immediately
    try:
        await bus.publish(_build_guardrail_update())
    except Exception:
        pass

    return JSONResponse(snap)


def _build_guardrail_data() -> dict:
    """Construct guardrail data matching /api/ops/risk-snapshot schema (defaults)."""
    return {
        "risk_level": "OK",
        "kill_switch": False,
        "downgrade_level": 0,
        "reason": "",
        "recovery_count": 0,
    }


def _build_guardrail_update() -> dict:
    """Build full guardrail_update event payload per protocol.
    
    Uses real snapshot data from _get_risk_snapshot_payload() to ensure
    WS events reflect current guardrail state.
    """
    snap = _get_risk_snapshot_payload()
    return {
        "type": "guardrail_update",
        "ts": int(time.time() * 1000),
        "trace_id": snap.get("trace_id") or "no-trace",
        "source": "guardrail",
        "severity": "info",
        "data": {
            "risk_level": snap.get("risk_level", "OK"),
            "kill_switch": bool(snap.get("kill_switch") is True),
            "downgrade_level": int(snap.get("downgrade_level") or 0),
            "reason": snap.get("reason", "") or "",
            "recovery_count": int(snap.get("recovery_count") or 0),
        },
    }


@app.get("/log-tail")
async def log_tail(lines: int = 50) -> PlainTextResponse:
    log_path = _latest_log_file()
    if not log_path:
        return PlainTextResponse("[no log file found]\n", status_code=404)
    return PlainTextResponse(_tail_lines(log_path, n=max(1, min(lines, 500))))


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/api/ops/hang-sub")
async def hang_subscribe() -> JSONResponse:
    """Create a hanging subscriber (for testing backpressure)."""
    try:
        q = await bus.subscribe()
        HUNG_SUBS.append(q)
        return JSONResponse({"status": "ok", "hung_subs": len(HUNG_SUBS)})
    except Exception:
        return JSONResponse({"status": "error"}, status_code=500)


@app.post("/api/ops/clear-hung-subs")
async def clear_hung_subs() -> JSONResponse:
    try:
        cnt = 0
        while HUNG_SUBS:
            q = HUNG_SUBS.pop()
            try:
                await bus.unsubscribe(q)
            except Exception:
                pass
            cnt += 1
        return JSONResponse({"status": "ok", "cleared": cnt})
    except Exception:
        return JSONResponse({"status": "error"}, status_code=500)
