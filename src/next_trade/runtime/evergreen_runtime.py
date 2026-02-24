import asyncio
import time
import json
from pathlib import Path

METRICS_PATH = Path("C:/projects/NEXT-TRADE/metrics/evergreen_metrics.jsonl")

# Global bus reference (will be injected from ops_web)
_broadcast_bus = None

def set_broadcast_bus(bus):
    """Set the broadcast bus reference from ops_web"""
    global _broadcast_bus
    _broadcast_bus = bus

async def run_runtime():
    """Async runtime loop for integration with FastAPI lifespan"""
    tick = 0
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        while True:
            tick += 1

            payload = {
                "ts": time.time(),
                "tick": tick,
                "status": "running"
            }

            # Write to metrics file
            with open(METRICS_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")

            # Broadcast via EventBus if available
            if _broadcast_bus:
                try:
                    await _broadcast_bus.publish({
                        "type": "runtime_tick",
                        "data": payload
                    })
                except Exception:
                    pass

            await asyncio.sleep(1)
    except asyncio.CancelledError:
        return

def runtime_loop():
    """Legacy sync wrapper for standalone execution"""
    asyncio.run(run_runtime())

if __name__ == "__main__":
    runtime_loop()
