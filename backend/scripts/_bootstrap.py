"""Runtime path helpers for backend maintenance scripts."""

from __future__ import annotations

from pathlib import Path
import sys


def ensure_backend_path() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    backend_path = str(backend_dir)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
