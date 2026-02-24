"""
Alert System

Multi-sink alerting: File (JSONL) + Slack (optional).
Used for entry/exit/error/kill_block notifications.

Supports async operations and batching for performance.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

try:
    import aiohttp
except ImportError:
    aiohttp = None


@dataclass
class AlertEvent:
    """Alert event to be emitted"""
    event_type: str  # ENTRY, EXIT, ERROR, KILL_BLOCK, DOWNGRADE_APPLIED, HEARTBEAT
    ts: int  # milliseconds
    symbol: str
    payload: dict  # Flexible dict with event-specific data


class FileAlertSink:
    """Write alerts to JSONL file"""

    def __init__(self, path: Path | str = "evidence/phase-s3-runtime/alerts.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def send(self, event: AlertEvent) -> bool:
        """Append alert to JSONL file"""
        try:
            line = json.dumps({
                "type": event.event_type,
                "ts": event.ts,
                "symbol": event.symbol,
                "payload": event.payload,
            }, default=str)

            with self.path.open("a") as f:
                f.write(line + "\n")

            return True
        except Exception as e:
            print(f"[FileAlertSink] Error: {e}")
            return False


class SlackWebhookSink:
    """Send alerts to Slack via webhook (optional)"""

    def __init__(self, url_env: str = "SLACK_WEBHOOK_URL"):
        self.webhook_url = os.getenv(url_env)
        self.enabled = bool(self.webhook_url)

    async def send(self, event: AlertEvent) -> bool:
        """Send alert to Slack webhook"""
        if not self.enabled or not aiohttp:
            return True  # Silently skip if not configured

        try:
            # Build Slack message
            color_map = {
                "ENTRY": "#36a64f",
                "EXIT": "#ff7f50",
                "ERROR": "#c41e3a",
                "KILL_BLOCK": "#8b0000",
                "DOWNGRADE_APPLIED": "#ffa500",
                "HEARTBEAT": "#0099ff",
            }

            color = color_map.get(event.event_type, "#999999")

            payload = {
                "attachments": [
                    {
                        "fallback": f"{event.event_type}: {event.symbol}",
                        "color": color,
                        "title": f"{event.event_type}",
                        "text": event.symbol,
                        "fields": [
                            {"title": "Time", "value": str(event.ts), "short": True},
                            {"title": "Type", "value": event.event_type, "short": True},
                            {"title": "Details", "value": json.dumps(event.payload, default=str)[:500], "short": False},
                        ],
                        "ts": event.ts // 1000,
                    }
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return resp.status == 200

        except Exception as e:
            print(f"[SlackWebhookSink] Error: {e}")
            return False


class AlertManager:
    """Centralized alert dispatcher"""

    def __init__(self, sinks: list = None):
        """
        Args:
            sinks: List of alert sinks (FileAlertSink, SlackWebhookSink, etc.)
        """
        self.sinks = sinks or [FileAlertSink()]

    async def send(
        self,
        event_type: str,
        symbol: str,
        payload: dict = None,
    ) -> bool:
        """
        Send alert to all configured sinks

        Args:
            event_type: ENTRY, EXIT, ERROR, KILL_BLOCK, DOWNGRADE_APPLIED, HEARTBEAT
            symbol: e.g., BTCUSDT
            payload: Event-specific data dict

        Returns:
            True if at least one sink succeeded
        """
        event = AlertEvent(
            event_type=event_type,
            ts=int(time.time() * 1000),
            symbol=symbol,
            payload=payload or {},
        )

        results = await asyncio.gather(
            *[sink.send(event) for sink in self.sinks],
            return_exceptions=True,
        )

        # Consider success if any sink succeeded or no exceptions
        success = any(r is True for r in results)

        # Log to console
        print(f"[Alert] {event_type} | {symbol} | {event.payload}")

        return success
