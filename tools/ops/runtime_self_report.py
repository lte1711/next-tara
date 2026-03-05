import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone


def now_ms() -> int:
    return int(time.time() * 1000)


def safe_getppid() -> int:
    # Windows에서도 Python 3.8+는 os.getppid 지원
    try:
        return os.getppid()
    except Exception:
        return -1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        help="Seconds to keep process alive for tree capture",
    )
    p.add_argument(
        "--tag",
        type=str,
        default="runtime_self_report",
        help="Tag for evidence correlation",
    )
    p.add_argument(
        "--out",
        type=str,
        default="",
        help="Optional output file path to append one-line JSON report",
    )
    args = p.parse_args()

    rec = {
        "ts_ms": now_ms(),
        "utc_iso": datetime.now(timezone.utc).isoformat(),
        "tag": args.tag,
        "pid": os.getpid(),
        "ppid": safe_getppid(),
        "argv": sys.argv,
        "python_version": sys.version,
        "platform": platform.platform(),
        "sys_executable": sys.executable,
        "sys_base_executable": getattr(sys, "_base_executable", None),
        "sys_prefix": getattr(sys, "prefix", None),
        "sys_base_prefix": getattr(sys, "base_prefix", None),
        "sys_real_prefix": getattr(sys, "real_prefix", None),
    }

    # 한 줄 JSON 출력(PS1에서 캡처)
    line = json.dumps(rec, ensure_ascii=False)
    print(line)
    if args.out:
        try:
            with open(args.out, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    # 트리 캡처 시간 확보
    time.sleep(max(0.0, args.sleep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
