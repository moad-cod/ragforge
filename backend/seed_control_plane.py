"""Compatibility wrapper for ``python seed_control_plane.py``.

Prefer ``python -m scripts.seed_control_plane`` from the backend directory.
"""

from scripts.seed_control_plane import main


if __name__ == "__main__":
    main()
