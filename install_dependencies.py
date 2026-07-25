import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REQUIREMENTS = ROOT / "requirements.txt"


def main() -> int:
    if not REQUIREMENTS.exists():
        print(f"Cannot find requirements file: {REQUIREMENTS}")
        return 1

    command = [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)]
    print("Installing dependencies...")
    print("Command:", " ".join(command))

    result = subprocess.run(command, cwd=str(ROOT))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
