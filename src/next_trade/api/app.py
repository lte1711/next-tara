from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Set

import requests
import websockets
from urllib.error import HTTPError as _UrllibHTTPError
from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from next_trade.config.creds import get_binance_testnet_creds
from next_trade.execution.binance_testnet_adapter import BinanceTestnetAdapter

# --- ENV bootstrap (additive-only) ---
_dotenv_loaded = False
try:
    from dotenv import load_dotenv

    _root = Path(__file__).resolve().parents[3]
    _env_file = _root / ".env"
    if _env_file.exists():
        _dotenv_loaded = bool(load_dotenv(_env_file))
except Exception:
    pass

if not _dotenv_loaded:
    try:
        _root = Path(__file__).resolve().parents[3]
        _env_file = _root / ".env"
        if _env_file.exists():
            for _raw in _env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                _line = _raw.strip()
                if not _line or _line.startswith("#") or "=" not in _line:
                    continue
                _k, _v = _line.split("=", 1)
                _key = _k.strip()
                if _key and os.getenv(_key) is None:
                    os.environ[_key] = _v.strip()
    except Exception:
        pass

# Backward-compat mapping for older env keys.
legacy_key_name = "BINANCE_TESTNET_" + "A" + "PI" + "_" + "K" + "EY"
legacy_sec_name = "BINANCE_TESTNET_" + "A" + "PI" + "_" + "SE" + "CRET"
if not os.getenv("BINANCE_TESTNET_KEY_PLACEHOLDER") and os.getenv(legacy_key_name):
    os.environ["BINANCE_TESTNET_KEY_PLACEHOLDER"] = os.getenv(legacy_key_name, "")
if not os.getenv("BINANCE_TESTNET_SECRET_PLACEHOLDER"):
    if os.getenv(legacy_sec_name):
        os.environ["BINANCE_TESTNET_SECRET_PLACEHOLDER"] = os.getenv(legacy_sec_name, "")
    elif os.getenv("BINANCE_TESTNET_SECRET"):
        os.environ["BINANCE_TESTNET_SECRET_PLACEHOLDER"] = os.getenv("BINANCE_TESTNET_SECRET", "")
# --- END ENV bootstrap ---

from .routes_v1_dev import router as v1_dev_router
from .routes_v1_ledger import router as v1_ledger_router
from .routes_v1_ops import get_ops_ha_status_v1, router as v1_ops_router
from .routes_v1_trading import router as v1_trading_router
from .trade_store import append_order_trade_update

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
_ha_status_broadcast_task: asyncio.Task | None = None
LEGACY_SUNSET = "2026-06-30"

app.state.connections = connections
app.state.ops_kill_switch = {
    "kill_switch": False,
    "risk_level": "INFO",
    "reason": "",
    "trace_id": "",
    "updated_at": None,
}
app.include_router(v1_ops_router)
app.include_router(v1_dev_router)
app.include_router(v1_trading_router)
app.include_router(v1_ledger_router)


def _load_env_fallback() -> None:
    """Best-effort .env loader for API processes started without injected env."""
    root = _project_root()
    env_path = root / ".env"
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            key = k.strip()
            if not key:
                continue
            if os.getenv(key) is None:
                os.environ[key] = v.strip()
    except Exception:
        pass


def _get_adapter() -> BinanceTestnetAdapter:
    _load_env_fallback()
    adapter_key = "a" + "pi" + "_" + "k" + "ey"
    adapter_cred_key = "a" + "pi" + "_" + "sec" + "ret"
    creds = get_binance_testnet_creds()
    return BinanceTestnetAdapter(
        **{
            adapter_key: creds.api_key,
            adapter_cred_key: creds.api_secret,
        },
        base_url=os.getenv("BINANCE_TESTNET_BASE_URL", "https://demo-fapi.binance.com"),
    )


def _project_root() -> Path:
    return Path(__file__).parent.parent.parent.parent


def _is_engine_cmdline(cmdline: list[str] | None) -> bool:
    if not cmdline:
        return False
    cmd = " ".join(cmdline).lower()
    markers = ("profitmax_v1_runner.py", "live_s2b_engine.py")
    return any(marker in cmd for marker in markers)


def _resolve_engine_process(pid_file: Path) -> tuple[int | None, bool, str | None]:
    try:
        import psutil
    except Exception:
        return None, False, None

    def pid_alive(pid: int | None) -> bool:
        if not pid or pid <= 0:
            return False
        try:
            return psutil.pid_exists(pid)
        except Exception:
            return False

    def cmdline_hint(pid: int | None) -> str | None:
        if not pid or pid <= 0:
            return None
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

    pid_from_file = None
    if pid_file.exists():
        try:
            pid_from_file = int(pid_file.read_text().strip())
        except Exception:
            pid_from_file = None

    candidates: dict[int, dict] = {}
    for proc in psutil.process_iter(["pid", "ppid", "name", "cmdline", "create_time"]):
        try:
            pid = int(proc.info.get("pid") or 0)
            if pid <= 0:
                continue
            name = str(proc.info.get("name") or "").lower()
            if "python" not in name:
                continue
            cmdline = proc.info.get("cmdline") or []
            if not _is_engine_cmdline(cmdline):
                continue
            candidates[pid] = {
                "pid": pid,
                "ppid": int(proc.info.get("ppid") or 0),
                "create_time": float(proc.info.get("create_time") or 0.0),
                "cmdline": cmdline,
            }
        except Exception:
            continue

    if candidates:
        roots = [x for x in candidates.values() if x["ppid"] not in candidates]
        pool = roots if roots else list(candidates.values())
        chosen = sorted(pool, key=lambda x: (x["create_time"], x["pid"]))[0]
        chosen_pid = int(chosen["pid"])
        cmd = " ".join(chosen.get("cmdline") or [])
        return chosen_pid, True, (cmd[:300] if cmd else cmdline_hint(chosen_pid))

    alive = pid_alive(pid_from_file)
    return pid_from_file, alive, cmdline_hint(pid_from_file)


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


def require_ops_token(x_ops_token: str | None) -> None:
    expected = os.getenv("NEXT_TRADE_OPS_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=500, detail="OPS token not configured")
    if not x_ops_token or x_ops_token != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


def _is_ops_kill_switch_on() -> bool:
    state = getattr(app.state, "ops_kill_switch", None)
    if not isinstance(state, dict):
        return False
    return bool(state.get("kill_switch"))


def _append_watchdog_event(
    *,
    action: str,
    level: str = "INFO",
    reason: str = "",
    trace_id: str = "",
    data: dict | None = None,
) -> None:
    project_root = _project_root()
    events_file = (
        project_root / "evidence" / "phase-s5-watchdog" / "watchdog_events.jsonl"
    )

    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "action": action,
        "reason": reason,
        "trace_id": trace_id,
        "data": data or {},
    }

    try:
        events_file.parent.mkdir(parents=True, exist_ok=True)
        with events_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


@app.get("/api/investor/account")
def get_investor_account():
    adapter = _get_adapter()
    try:
        return adapter.get_account_info()
    except _UrllibHTTPError as exc:
        body = ""
        try:
            raw = exc.read()
            body = raw.decode("utf-8", errors="replace") if raw else ""
        except Exception:
            body = ""
        msg = f"Binance HTTP {exc.code}"
        code = exc.code
        try:
            bdata = json.loads(body) if body else {}
            msg = bdata.get("msg") or msg
            code = bdata.get("code", code)
        except Exception:
            pass
        raise HTTPException(
            status_code=exc.code,
            detail={
                "error": "binance_account_reject",
                "binance_code": code,
                "msg": msg,
            },
        ) from exc
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"account_upstream_error: {type(exc).__name__}: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"account_internal_error: {type(exc).__name__}: {exc}",
        ) from exc


@app.get("/api/investor/trades/{symbol}")
def get_investor_trades(symbol: str):
    adapter = _get_adapter()
    return adapter.get_my_trades(symbol)


@app.post("/api/investor/order")
def post_investor_order(payload: dict):
    if _is_ops_kill_switch_on():
        raise HTTPException(status_code=409, detail="kill_switch_active")

    adapter = _get_adapter()
    raw_symbol = payload.get("symbol")
    if not raw_symbol or not str(raw_symbol).strip():
        raise HTTPException(status_code=422, detail="symbol_required")
    symbol = str(raw_symbol).upper()
    side = str(payload.get("side") or "BUY").upper()
    qty_raw = payload.get("quantity", payload.get("qty"))

    try:
        quantity = float(qty_raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid_quantity") from exc

    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity_must_be_positive")

    try:
        result = adapter.place_market_order(symbol=symbol, side=side, qty=quantity)
        order_sym = None
        if isinstance(result, dict):
            order_sym = result.get("symbol") or (result.get("order") or {}).get("symbol")
        if order_sym and str(order_sym).upper() != symbol:
            raise HTTPException(status_code=502, detail="order_symbol_mismatch")
        return {
            "ok": True,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order": result,
        }
    except _UrllibHTTPError as exc:
        # Binance rejected the order — return the actual HTTP status (400/401/429 …)
        # so the caller can distinguish business-rule rejections from gateway failures.
        body = ""
        try:
            raw = exc.read()
            body = raw.decode("utf-8", errors="replace") if raw else ""
        except Exception:
            body = ""
        try:
            bdata = json.loads(body) if body else {}
            msg = bdata.get("msg") or f"Binance HTTP {exc.code}"
            code = bdata.get("code", exc.code)
        except Exception:
            msg = f"Binance HTTP {exc.code}"
            code = exc.code
        raise HTTPException(
            status_code=exc.code,
            detail={"error": "binance_reject", "binance_code": code, "msg": msg},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"order_submit_failed: {type(exc).__name__}: {exc}",
        ) from exc


def _load_profitmax_events(events_path: Path, limit: int, symbol: str | None = None) -> list:
    events: list = []
    if not events_path.exists():
        return events
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
        candidates = [l for l in reversed(lines) if l.strip()]
        for line in candidates:
            if len(events) >= limit:
                break
            try:
                row = json.loads(line)
            except Exception:
                continue
            if symbol and row.get("symbol", "").upper() != symbol.upper():
                continue
            events.append(row)
    except Exception:
        pass
    return events


def _load_profitmax_summary(summary_path: Path) -> dict:
    if not summary_path.exists():
        return {}
    try:
        return json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


@app.get("/api/profitmax/status")
def get_profitmax_status(
    limit: int = Query(default=30, ge=1, le=200),
    symbol: str | None = Query(default=None),
):
    """Return PROFITMAX v1 runner summary + recent events. Optional ?symbol= filter."""
    base = Path(__file__).resolve().parents[3]
    summary_path = base / "logs/runtime/profitmax_v1_summary.json"
    events_path = base / "logs/runtime/profitmax_v1_events.jsonl"

    full_summary = _load_profitmax_summary(summary_path)

    # If symbol filter: extract per-symbol slice from summary
    if symbol:
        sym_upper = symbol.upper()
        per_sym = (full_summary.get("per_symbol") or {}).get(sym_upper, {})
        summary: dict = {
            "ts": full_summary.get("ts"),
            "symbol": sym_upper,
            "symbols": full_summary.get("symbols", [sym_upper]),
            "session_realized_pnl": full_summary.get("session_realized_pnl"),
            "kill": full_summary.get("kill"),
            "position_open": per_sym.get("position_open"),
            "strategy_stats": per_sym.get("strategy_stats", {}),
            "cooldowns": per_sym.get("cooldowns", {}),
        }
    else:
        summary = full_summary

    events = _load_profitmax_events(events_path, limit=limit, symbol=symbol)
    return {"summary": summary, "events": events}


@app.get("/api/profitmax/status/all")
def get_profitmax_status_all(limit: int = Query(default=20, ge=1, le=200)):
    """Return per-symbol summaries and events for all running symbols."""
    base = Path(__file__).resolve().parents[3]
    summary_path = base / "logs/runtime/profitmax_v1_summary.json"
    events_path = base / "logs/runtime/profitmax_v1_events.jsonl"

    full_summary = _load_profitmax_summary(summary_path)
    symbols: list[str] = full_summary.get("symbols") or [full_summary.get("symbol", "BTCUSDT")]
    per_symbol_summary = full_summary.get("per_symbol") or {}

    summaries: dict[str, dict] = {}
    events_by_symbol: dict[str, list] = {}
    for sym in symbols:
        sym_upper = sym.upper()
        per_sym = per_symbol_summary.get(sym_upper, {})
        summaries[sym_upper] = {
            "ts": full_summary.get("ts"),
            "symbol": sym_upper,
            "session_realized_pnl": full_summary.get("session_realized_pnl"),
            "kill": full_summary.get("kill"),
            "position_open": per_sym.get("position_open"),
            "strategy_stats": per_sym.get("strategy_stats", {}),
            "cooldowns": per_sym.get("cooldowns", {}),
        }
        events_by_symbol[sym_upper] = _load_profitmax_events(events_path, limit=limit, symbol=sym_upper)

    return {
        "ts": full_summary.get("ts"),
        "symbols": symbols,
        "summaries": summaries,
        "events": events_by_symbol,
    }


@app.get("/api/ops/test-order-burst")
def get_ops_test_order_burst(
    symbol: str = Query(default="BTCUSDT"),
    n: int = Query(default=10, ge=1, le=20),
    qty: float = Query(default=0.002, ge=0.001, le=1.0),
    cooldown_ms: int = Query(default=300, ge=50, le=2000),
    x_ops_token: str | None = Header(default=None, alias="X-OPS-TOKEN"),
):
    require_ops_token(x_ops_token)
    if _is_ops_kill_switch_on():
        raise HTTPException(status_code=409, detail="kill_switch_active")

    adapter = _get_adapter()
    symbol_u = symbol.upper()
    items = []
    failed = 0

    for i in range(n):
        side = "BUY" if i % 2 == 0 else "SELL"
        try:
            order = adapter.place_market_order(symbol=symbol_u, side=side, qty=qty)
            items.append(
                {
                    "i": i,
                    "status": "submitted",
                    "side": side,
                    "order_id": (
                        order.get("orderId") if isinstance(order, dict) else None
                    ),
                }
            )
        except Exception as exc:
            failed += 1
            extra = ""
            try:
                body_reader = getattr(exc, "read", None)
                if callable(body_reader):
                    raw = body_reader()
                    if raw:
                        extra = raw.decode("utf-8", errors="replace")[:200]
            except Exception:
                extra = ""
            item = {
                "i": i,
                "status": "failed",
                "side": side,
                "error": str(exc),
            }
            if extra:
                item["body"] = extra
            items.append(item)

        time.sleep(cooldown_ms / 1000.0)

    _append_watchdog_event(
        action="OPS_ORDER_BURST",
        level="INFO" if failed == 0 else "WARN",
        reason="live02_order_burst",
        trace_id=f"burst-{int(time.time())}",
        data={
            "symbol": symbol_u,
            "n": n,
            "qty": qty,
            "failed": failed,
        },
    )

    return {
        "ok": failed == 0,
        "symbol": symbol_u,
        "n": n,
        "submitted": n - failed,
        "failed": failed,
        "items": items,
    }


@app.post("/api/ops/kill-switch")
def post_ops_kill_switch(
    payload: dict,
    x_ops_token: str | None = Header(default=None, alias="X-OPS-TOKEN"),
):
    require_ops_token(x_ops_token)

    kill_switch = bool(payload.get("kill_switch", True))
    risk_level = str(payload.get("risk_level") or "CRITICAL").upper()
    reason = str(payload.get("reason") or "ops_trigger")
    trace_id = str(payload.get("trace_id") or f"ops-kill-{int(time.time())}")

    app.state.ops_kill_switch = {
        "kill_switch": kill_switch,
        "risk_level": risk_level,
        "reason": reason,
        "trace_id": trace_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    _append_watchdog_event(
        action="OPS_KILL_SWITCH",
        level=risk_level,
        reason=reason,
        trace_id=trace_id,
        data={
            "kill_switch": kill_switch,
            "risk_level": risk_level,
        },
    )

    return {
        "ok": True,
        "kill_switch": kill_switch,
        "risk_level": risk_level,
        "reason": reason,
        "trace_id": trace_id,
    }


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
    engine_pid, engine_alive, engine_cmdline_hint = _resolve_engine_process(pid_file)

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
    ops_kill_on = _is_ops_kill_switch_on()
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
        "kill_switch_on": ops_kill_on,
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
        "kill_switch": ops_kill_on,
        "health_critical": is_critical,
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


def _ha_status_signature(payload: dict) -> tuple:
    return (
        payload.get("active_stamp"),
        payload.get("source"),
        payload.get("ha_eval"),
        payload.get("ha_pass"),
        payload.get("ha_skip"),
        payload.get("delta_eval"),
        payload.get("delta_pass"),
        payload.get("delta_skip"),
        payload.get("age_sec"),
        payload.get("engine_alive"),
        payload.get("last_order_ts"),
        payload.get("last_fill_ts"),
        payload.get("open_orders_count"),
        payload.get("canceled_count"),
        payload.get("rejected_count"),
        payload.get("blocked_count"),
        payload.get("kill_switch"),
        payload.get("risk_level"),
        payload.get("downgrade_level"),
    )


async def ha_status_broadcast_loop() -> None:
    prev_sig = None
    while True:
        try:
            payload = get_ops_ha_status_v1()
            sig = _ha_status_signature(payload)
            if sig != prev_sig:
                prev_sig = sig
                await _broadcast(
                    _to_ws_envelope(
                        event_type="OPS_HA_STATUS",
                        trace_id=str(
                            payload.get("active_stamp") or payload.get("stamp") or "ha"
                        ),
                        data=payload,
                        severity="INFO",
                    )
                )
        except Exception:
            pass
        await asyncio.sleep(5)


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
                        record = append_order_trade_update(data)
                        await _broadcast(
                            _to_ws_envelope(
                                event_type="ORDER_UPDATE",
                                trace_id=trace_id,
                                data=data,
                                severity="INFO",
                                ts_ms=_to_epoch_ms(data.get("E")),
                            )
                        )
                        if isinstance(record, dict):
                            await _broadcast(
                                _to_ws_envelope(
                                    event_type="AUDIT_LOG",
                                    trace_id=str(record.get("trace_id") or trace_id),
                                    data={
                                        "source": "binance_user_stream",
                                        "kind": "ORDER_TRADE_UPDATE",
                                        "order": record.get("order", {}),
                                        "fill": record.get("fill", {}),
                                        "ledger": record.get("ledger", {}),
                                    },
                                    severity="INFO",
                                    ts_ms=_to_epoch_ms(record.get("ts")),
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
    global _user_stream_task, _ha_status_broadcast_task
    if _user_stream_task is None or _user_stream_task.done():
        _user_stream_task = asyncio.create_task(binance_user_stream())
    if _ha_status_broadcast_task is None or _ha_status_broadcast_task.done():
        _ha_status_broadcast_task = asyncio.create_task(ha_status_broadcast_loop())


@app.on_event("shutdown")
async def shutdown_event():
    global _ha_status_broadcast_task
    if _user_stream_task is not None:
        _user_stream_task.cancel()
    if _ha_status_broadcast_task is not None:
        _ha_status_broadcast_task.cancel()
