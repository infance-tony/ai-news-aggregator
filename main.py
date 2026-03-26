from pathlib import Path
import sys

import uvicorn


def _ensure_project_venv() -> None:
    project_root = Path(__file__).resolve().parent
    expected_python = (project_root / ".venv" / "Scripts" / "python.exe").resolve()
    current_python = Path(sys.executable).resolve()

    if expected_python.exists() and current_python != expected_python:
        raise SystemExit(
            "Wrong Python interpreter detected. Run with: .venv/Scripts/python main.py"
        )

if __name__ == "__main__":
    _ensure_project_venv()
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=True)
