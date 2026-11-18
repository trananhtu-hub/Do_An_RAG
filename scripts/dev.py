"""Chạy đồng thời backend FastAPI (cổng 8000) và frontend Next.js (cổng 3000)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IS_WINDOWS = sys.platform == "win32"
VENV_BIN = ROOT / ".venv" / ("Scripts" if IS_WINDOWS else "bin")


def main() -> int:
    backend = subprocess.Popen(
        [str(VENV_BIN / "uvicorn"), "app.main:app", "--reload", "--port", "8000"],
        cwd=ROOT / "backend",
    )
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=ROOT / "frontend",
        shell=IS_WINDOWS,
    )
    print("Backend: http://localhost:8000  |  Frontend: http://localhost:3000")
    try:
        return max(backend.wait(), frontend.wait())
    except KeyboardInterrupt:
        backend.terminate()
        frontend.terminate()
        return 0


if __name__ == "__main__":
    sys.exit(main())
