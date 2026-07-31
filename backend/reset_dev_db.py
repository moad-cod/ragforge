"""Compatibility wrapper for ``python reset_dev_db.py``.

Prefer ``python -m scripts.reset_dev_db`` from the backend directory.
"""

from scripts import reset_dev_db


if __name__ == "__main__":
    reset_dev_db.main()
