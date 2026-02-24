"""
Risk Snapshot Provider

Reads live_obs.jsonl to get current risk state (kill_switch, downgrade_level).
Used by engine to gate entries and adjust positon sizes.

Supports cached reads (optional) for performance.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RiskSnapshot:
    """Current risk state from live_obs.jsonl"""
    kill_switch: bool
    downgrade_level: int
    risk_level: str
    ts: int
    source: str = "live_obs.jsonl"


class RiskSnapshotProvider:
    """Reads risk state from live_obs.jsonl"""

    def __init__(
        self,
        obs_file: Path | str = "metrics/live_obs.jsonl",
        cache_sec: float = 5.0,
    ):
        """
        Args:
            obs_file: Path to live_obs.jsonl
            cache_sec: Cache duration (default 5s to avoid fileI/O churn)
        """
        self.obs_file = Path(obs_file)
        self.cache_sec = cache_sec
        self.last_snap: Optional[RiskSnapshot] = None
        self.last_read_ts = 0.0

    def get_latest(self) -> RiskSnapshot:
        """
        Get latest risk snapshot from live_obs.jsonl

        Returns cached value if fresh (< cache_sec old), else reads file.
        Falls back to safe defaults (kill=false, downgrade=0) on read error.
        """
        now = time.time()

        # Return cached if fresh
        if self.last_snap and (now - self.last_read_ts) < self.cache_sec:
            return self.last_snap

        # Read fresh from file
        snap = self._read_latest_line()
        self.last_snap = snap
        self.last_read_ts = now
        return snap

    def _read_latest_line(self) -> RiskSnapshot:
        """
        Read last line from live_obs.jsonl and parse risk state

        Safe defaults if file missing or parse fails:
        - kill_switch=false
        - downgrade_level=0
        """
        if not self.obs_file.exists():
            return RiskSnapshot(
                kill_switch=False,
                downgrade_level=0,
                risk_level="normal",
                ts=int(time.time() * 1000),
            )

        try:
            # Read last 2KB to avoid loading huge file
            with self.obs_file.open("rb") as f:
                f.seek(0, 2)  # Seek to end
                size = f.tell()
                read_size = min(2048, size)
                f.seek(-read_size, 2)
                tail = f.read().decode(errors="ignore")

            # Parse last line
            lines = tail.strip().split("\n")
            if not lines:
                return self._safe_default()

            last_line = lines[-1]
            if not last_line:
                return self._safe_default()

            data = json.loads(last_line)

            # Extract risk fields (flexible key names)
            kill_switch = data.get("kill_switch", data.get("killed", False))
            downgrade_level = int(data.get("downgrade_level", data.get("level", 0)))
            risk_level = data.get("risk_level", "normal")
            ts = int(data.get("ts", time.time() * 1000))

            return RiskSnapshot(
                kill_switch=bool(kill_switch),
                downgrade_level=downgrade_level,
                risk_level=risk_level,
                ts=ts,
            )

        except Exception as e:
            print(f"[RiskSnapshot] Error reading {self.obs_file}: {e}")
            return self._safe_default()

    @staticmethod
    def _safe_default() -> RiskSnapshot:
        """Safe defaults when file/parse fails"""
        return RiskSnapshot(
            kill_switch=False,
            downgrade_level=0,
            risk_level="normal",
            ts=int(time.time() * 1000),
        )
