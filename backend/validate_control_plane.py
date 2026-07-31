"""Compatibility wrapper for ``python validate_control_plane.py``.

Prefer ``python -m scripts.validate_control_plane`` from the backend directory.
"""

from scripts.validate_control_plane import main


if __name__ == "__main__":
    main()
