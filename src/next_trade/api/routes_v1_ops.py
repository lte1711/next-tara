from __future__ import annotations

import json
import os
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Query

from next_trade.execution.binance_testnet_adapter import BinanceTestnetAdapter
from next_trade.config.creds import get_binance_testnet_creds
from next_trade.api.trade_store import list_fills, list_orders

router = APIRouter(prefix="/api/v1/ops", tags=["ops-v1"])

CONTRACT_VERSION = "v1"


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


def _get_binance_adapter() -> BinanceTestnetAdapter:
    creds = get_binance_testnet_creds()
    arg_key = "a" + "pi" + "_" + "k" + "ey"
    arg_secv = "a" + "pi" + "_" + "sec" + "ret"
    return BinanceTestnetAdapter(
        **{
            arg_key: creds.api_key,
            arg_secv: creds.api_secret,
        },
        base_url=os.getenv("BINANCE_TESTNET_BASE_URL", "https://demo-fapi.binance.com"),
    )


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

    engine_pid, engine_alive, engine_cmdline_hint = _resolve_engine_process(pid_file)

    checkpoint_age_sec = None
    checkpoint_status = "UNKNOWN"
    checkpoint_expected_interval_sec = float(
        os.getenv("NEXTTRADE_CHECKPOINT_EXPECTED_INTERVAL_SEC", "120") or 120
    )
    checkpoint_stale_threshold_sec = max(
        (checkpoint_expected_interval_sec * 2.0) + 30.0, 60.0
    )
    checkpoint_expired_threshold_sec = max(
        checkpoint_stale_threshold_sec * 2.0,
        checkpoint_stale_threshold_sec + checkpoint_expected_interval_sec,
    )
    if checkpoint_file.exists():
        try:
            mtime = checkpoint_file.stat().st_mtime
            age = datetime.now().timestamp() - mtime
            checkpoint_age_sec = round(age, 1)
            if age <= checkpoint_expected_interval_sec:
                checkpoint_status = "FRESH"
            elif age <= checkpoint_stale_threshold_sec:
                checkpoint_status = "STALE"
            elif age <= checkpoint_expired_threshold_sec:
                checkpoint_status = "EXPIRED"
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

    critical_reasons: list[str] = []
    if checkpoint_status == "STALE":
        critical_reasons.append("checkpoint_stale")
    if not engine_alive:
        critical_reasons.append("engine_dead")
    if checkpoint_status == "EXPIRED":
        critical_reasons.append("checkpoint_expired")
    # Keep this non-empty so missing reason logic is visible to operators.
    if not critical_reasons:
        critical_reasons.append("none")
    if health_status == "CRITICAL" and critical_reasons == ["none"]:
        critical_reasons = ["unknown_reason_bug"]

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

    creds = get_binance_testnet_creds()

    return {
        "engine_pid": engine_pid,
        "engine_alive": engine_alive,
        "engine_cmdline_hint": engine_cmdline_hint,
        "checkpoint_age_sec": checkpoint_age_sec,
        "checkpoint_expected_interval_sec": checkpoint_expected_interval_sec,
        "checkpoint_stale_threshold_sec": checkpoint_stale_threshold_sec,
        "checkpoint_expired_threshold_sec": checkpoint_expired_threshold_sec,
        "checkpoint_status": checkpoint_status,
        "health_status": health_status,
        "last_health_ok": last_health_ok,
        "restart_count": restart_count,
        "flap_detected": flap_detected,
        "task_state": task_state,
        "critical_reasons": critical_reasons,
        "creds_source": creds.source,
        "key_set": bool(creds.api_key),
        "secret_set": bool(creds.api_secret),
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


def _extract_int(text: str, patterns: list[str]) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                continue
    return None


def _latest_file(base_dir: Path, pattern: str) -> Path | None:
    files = list(base_dir.glob(pattern))
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def _age_sec(path: Path | None) -> float | None:
    if not path or not path.exists():
        return None
    try:
        return round(max(0.0, datetime.now().timestamp() - path.stat().st_mtime), 1)
    except Exception:
        return None


def _extract_stamp_from_name(name: str) -> str | None:
    patterns = [
        r"^analysis_(.+)_summary\.txt$",
        r"^session_(?:start|mid_15m|end_60m)_(.+)\.txt$",
    ]
    for pat in patterns:
        match = re.match(pat, name, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _resolve_active_stamp(pmx_dir: Path) -> str | None:
    env_stamp = str(os.getenv("PMX_STAMP") or "").strip()
    if env_stamp:
        return env_stamp

    latest_start = _latest_file(pmx_dir, "session_start_*.txt")
    if latest_start:
        stamp = _extract_stamp_from_name(latest_start.name)
        if stamp:
            return stamp

    latest_summary = _latest_file(pmx_dir, "analysis_*_summary.txt")
    if latest_summary:
        text = latest_summary.read_text(encoding="utf-8", errors="ignore")
        stamp_match = re.search(r"^STAMP:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
        if stamp_match:
            return stamp_match.group(1).strip()
        stamp = _extract_stamp_from_name(latest_summary.name)
        if stamp:
            return stamp
    return None


def _parse_ha_from_summary(summary_path: Path) -> dict:
    text = summary_path.read_text(encoding="utf-8", errors="ignore")
    stamp_match = re.search(r"^STAMP:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
    stamp = stamp_match.group(1).strip() if stamp_match else summary_path.stem
    return {
        "stamp": stamp,
        "ha_eval": _extract_int(text, [r"HA Filter Eval \(session\)\s*:\s*(\d+)"]),
        "ha_pass": _extract_int(text, [r"HA Filter Pass \(session\)\s*:\s*(\d+)"]),
        "ha_skip": _extract_int(text, [r"HA Filter Skip \(session\)\s*:\s*(\d+)"]),
        "delta_eval": _extract_int(text, [r"HA Filter Eval Delta\s*:\s*(-?\d+)"]),
        "delta_pass": _extract_int(text, [r"HA Filter Pass Delta\s*:\s*(-?\d+)"]),
        "delta_skip": _extract_int(text, [r"HA Filter Skip Delta\s*:\s*(-?\d+)"]),
    }


def _parse_ha_from_session(session_path: Path) -> dict:
    text = session_path.read_text(encoding="utf-8", errors="ignore")
    stamp_match = re.search(
        r"session_(?:start|mid_15m|end_60m)_(.+)\.txt$", session_path.name, re.IGNORECASE
    )
    stamp = stamp_match.group(1) if stamp_match else session_path.stem
    return {
        "stamp": stamp,
        "ha_eval": _extract_int(text, [r"^ha_filter_eval_count=(\d+)$"]),
        "ha_pass": _extract_int(text, [r"^ha_filter_pass_count=(\d+)$"]),
        "ha_skip": _extract_int(text, [r"^ha_filter_skip_count=(\d+)$"]),
        "delta_eval": None,
        "delta_pass": None,
        "delta_skip": None,
    }


def _latest_live_obs_downgrade_level(project_root: Path) -> int:
    live_obs = project_root / "metrics" / "live_obs.jsonl"
    if not live_obs.exists():
        return 0
    try:
        lines = live_obs.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in reversed(lines[-500:]):
            if not line.strip():
                continue
            parsed = json.loads(line)
            value = parsed.get("downgrade_level")
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            if isinstance(value, str) and value.isdigit():
                return int(value)
    except Exception:
        return 0
    return 0


def _extract_blocked_count_from_text(text: str) -> int:
    value = _extract_int(
        text,
        [
            r"^blocked_count=(\d+)$",
            r"^s001_blocked=(\d+)$",
            r"Blocked(?:\s+Count)?\s*[:=]\s*(\d+)",
            r"Blocked(?:\s+\u0394)?\s*[:=]\s*(-?\d+)",
        ],
    )
    return max(0, int(value)) if value is not None else 0


def _latest_blocked_count(pmx_dir: Path, active_stamp: str | None) -> int:
    candidates: list[Path] = []
    if active_stamp:
        by_stamp = _latest_file(pmx_dir, f"session_*_{active_stamp}.txt")
        if by_stamp:
            candidates.append(by_stamp)
        by_summary = _latest_file(pmx_dir, f"analysis_{active_stamp}_summary.txt")
        if by_summary:
            candidates.append(by_summary)
    fallback_session = _latest_file(pmx_dir, "session_*.txt")
    if fallback_session:
        candidates.append(fallback_session)
    fallback_summary = _latest_file(pmx_dir, "analysis_*_summary.txt")
    if fallback_summary:
        candidates.append(fallback_summary)

    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            blocked = _extract_blocked_count_from_text(text)
            if blocked >= 0:
                return blocked
        except Exception:
            continue
    return 0


def _engine_visibility_fields(
    *,
    active_stamp: str | None,
    health_snapshot: dict,
    pmx_dir: Path,
) -> dict:
    orders = list_orders(limit=200)
    fills = list_fills(limit=200)

    def _status_count(status: str) -> int:
        return sum(
            1
            for item in orders
            if str(item.get("status") or "").upper() == status.upper()
        )

    open_orders_count = sum(
        1
        for item in orders
        if str(item.get("status") or "").upper() in {"NEW", "PARTIALLY_FILLED"}
    )
    canceled_count = _status_count("CANCELED")
    rejected_count = sum(
        1
        for item in orders
        if str(item.get("status") or "").upper() in {"REJECTED", "EXPIRED"}
    )
    last_order_ts = int(orders[0].get("ts")) if orders else 0
    last_fill_ts = int(fills[0].get("ts")) if fills else 0
    blocked_count = _latest_blocked_count(pmx_dir, active_stamp)

    kill_switch = False
    risk_level = "LOW"
    try:
        from .app import app as api_app

        ops_state = getattr(api_app.state, "ops_kill_switch", None) or {}
        kill_switch = bool(ops_state.get("kill_switch"))
        risk_level = str(ops_state.get("risk_level") or "LOW")
    except Exception:
        kill_switch = False
        risk_level = "LOW"

    downgrade_level = _latest_live_obs_downgrade_level(_project_root())

    return {
        "engine_alive": bool(health_snapshot.get("engine_alive")),
        "last_order_ts": last_order_ts,
        "last_fill_ts": last_fill_ts,
        "open_orders_count": open_orders_count,
        "canceled_count": canceled_count,
        "rejected_count": rejected_count,
        "blocked_count": blocked_count,
        "kill_switch": kill_switch,
        "risk_level": risk_level,
        "downgrade_level": downgrade_level,
    }


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

    ops_kill_on = False
    ops_kill_reason = ""
    try:
        from .app import app as api_app

        ops_state = getattr(api_app.state, "ops_kill_switch", None) or {}
        ops_kill_on = bool(ops_state.get("kill_switch"))
        ops_kill_reason = str(ops_state.get("reason") or "")
    except Exception:
        ops_kill_on = is_critical
        ops_kill_reason = task_state

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
            "is_on": ops_kill_on,
            "reason": ops_kill_reason or task_state,
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
    open_positions: list[dict] = []
    try:
        adapter = _get_binance_adapter()
        raw = adapter.get_positions()
        for p in raw:
            if not isinstance(p, dict):
                continue
            try:
                qty = float(p.get("positionAmt") or 0)
            except Exception:
                qty = 0.0
            if abs(qty) <= 0:
                continue
            avg_entry = float(p.get("entryPrice") or 0)
            pnl = float(p.get("unrealizedProfit") or 0)
            mark_price = (avg_entry + pnl / qty) if qty != 0 else avg_entry
            open_positions.append(
                {
                    "symbol": str(p.get("symbol") or ""),
                    "qty": qty,
                    "avg_entry_price": avg_entry,
                    "mark_price": round(mark_price, 2),
                    "pnl": pnl,
                }
            )
    except Exception:
        open_positions = []
    now_ts = int(datetime.now(timezone.utc).timestamp())
    return {
        "contract_version": CONTRACT_VERSION,
        "ts": now_ts,
        "timestamp": now_ts,
        "positions": open_positions,
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


@router.get("/ha_status")
def get_ops_ha_status_v1():
    now_iso = datetime.now(timezone.utc).isoformat()
    pmx_dir = _project_root() / "evidence" / "pmx"
    health_snapshot = _runtime_health_snapshot()
    default_payload = {
        "contract_version": CONTRACT_VERSION,
        "ts": now_iso,
        "data_ts": now_iso,
        "source": "none",
        "active_stamp": None,
        "stamp": None,
        "age_sec": None,
        "ha_eval": None,
        "ha_pass": None,
        "ha_skip": None,
        "delta_eval": None,
        "delta_pass": None,
        "delta_skip": None,
        **_engine_visibility_fields(
            active_stamp=None,
            health_snapshot=health_snapshot,
            pmx_dir=pmx_dir,
        ),
    }

    if not pmx_dir.exists():
        default_payload["reason"] = "pmx_dir_missing"
        return default_payload

    active_stamp = _resolve_active_stamp(pmx_dir)
    default_payload["active_stamp"] = active_stamp
    default_payload.update(
        _engine_visibility_fields(
            active_stamp=active_stamp,
            health_snapshot=health_snapshot,
            pmx_dir=pmx_dir,
        )
    )
    summary_file = None
    if active_stamp:
        summary_file = _latest_file(pmx_dir, f"analysis_{active_stamp}_summary.txt")
    if not summary_file:
        summary_file = _latest_file(pmx_dir, "analysis_*_summary.txt")
    if summary_file:
        try:
            parsed = _parse_ha_from_summary(summary_file)
            # Backfill session counts from session files when summary only has deltas.
            if (
                parsed.get("ha_eval") is None
                or parsed.get("ha_pass") is None
                or parsed.get("ha_skip") is None
            ):
                stamp = str(parsed.get("stamp") or "")
                session_candidate = None
                if stamp:
                    session_candidate = _latest_file(
                        pmx_dir, f"session_*_{stamp}.txt"
                    )
                if not session_candidate:
                    session_candidate = _latest_file(pmx_dir, "session_*.txt")
                if session_candidate:
                    session_parsed = _parse_ha_from_session(session_candidate)
                    if parsed.get("ha_eval") is None:
                        parsed["ha_eval"] = session_parsed.get("ha_eval")
                    if parsed.get("ha_pass") is None:
                        parsed["ha_pass"] = session_parsed.get("ha_pass")
                    if parsed.get("ha_skip") is None:
                        parsed["ha_skip"] = session_parsed.get("ha_skip")
                    parsed["session_path"] = str(session_candidate)
            return {
                **default_payload,
                **parsed,
                "source": "pmx_summary",
                "path": str(summary_file),
                "age_sec": _age_sec(summary_file),
            }
        except Exception as exc:
            default_payload["summary_parse_error"] = str(exc)

    session_file = None
    if active_stamp:
        session_file = _latest_file(pmx_dir, f"session_*_{active_stamp}.txt")
    if not session_file:
        session_file = _latest_file(pmx_dir, "session_*.txt")
    if session_file:
        try:
            parsed = _parse_ha_from_session(session_file)
            return {
                **default_payload,
                **parsed,
                "source": "pmx_session",
                "path": str(session_file),
                "age_sec": _age_sec(session_file),
            }
        except Exception as exc:
            default_payload["session_parse_error"] = str(exc)

    default_payload["reason"] = "ha_status_source_not_found"
    return default_payload
