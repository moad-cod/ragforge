"""Compatibility wrapper for ``python cleanup.py``.

Prefer ``python -m scripts.cleanup`` from the backend directory.
"""

from scripts import cleanup


if __name__ == "__main__":
    cleanup.main()
