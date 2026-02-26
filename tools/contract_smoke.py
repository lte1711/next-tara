from __future__ import annotations

import sys
from urllib.error import URLError
from urllib.request import urlopen

BASE = "http://127.0.0.1:8100"
ENDPOINTS = [
    "/api/v1/ops/health",
    "/api/v1/ops/state",
    "/api/v1/ops/positions",
    "/api/v1/ops/risks?limit=20",
]


def main() -> int:
    failed = False
    for path in ENDPOINTS:
        url = f"{BASE}{path}"
        try:
            with urlopen(url, timeout=10) as response:
                status = response.getcode()
            print(f"{url} -> {status}")
            if status != 200:
                failed = True
        except URLError as exc:
            failed = True
            print(f"{url} -> FAIL {exc}")

    if failed:
        print("contract smoke FAIL")
        return 2

    print("contract smoke PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
