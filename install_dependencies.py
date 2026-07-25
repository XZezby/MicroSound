#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQ = ROOT / "requirements.txt"


def main() -> int:
    if not REQ.exists():
        print(f"Requirements file not found: {REQ}")
        return 1

    cmd = [sys.executable, "-m", "pip", "install", "-r", str(REQ)]
    print("Installing dependencies...")
    print(" ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
