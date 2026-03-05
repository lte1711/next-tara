from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(r"C:\projects\NEXT-TRADE")
ENGINE_PY = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
ENGINE_SCRIPT = PROJECT_ROOT / "archive_legacy" / "ops_scripts" / "profitmax_v1_runner.py"
LOG_PATH = PROJECT_ROOT / "logs" / "runtime" / "engine_supervisor.log"
RESTART_DELAY_SEC = 5


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(msg: str) -> None:
    line = f"[{_utc_iso()}] {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")
    except Exception:
        pass


def _build_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    env["PATH"] = str(ENGINE_PY.parent) + ";" + env.get("PATH", "")
    return env


def _start_engine() -> subprocess.Popen:
    cmd = [str(ENGINE_PY), str(ENGINE_SCRIPT)]
    _log(f"ENGINE_SUPERVISOR: starting engine cmd={' '.join(cmd)}")
    return subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), env=_build_env())


def main() -> int:
    if not ENGINE_PY.exists():
        _log(f"ENGINE_SUPERVISOR: missing interpreter {ENGINE_PY}")
        return 2
    if not ENGINE_SCRIPT.exists():
        _log(f"ENGINE_SUPERVISOR: missing script {ENGINE_SCRIPT}")
        return 2

    while True:
        proc = _start_engine()
        code = proc.wait()
        _log(f"ENGINE_SUPERVISOR: engine stopped exit_code={code}")
        _log(f"ENGINE_SUPERVISOR: restart in {RESTART_DELAY_SEC}s")
        time.sleep(RESTART_DELAY_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
