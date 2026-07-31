"""Compatibility wrapper for ``python create_tables.py``.

Prefer ``python -m scripts.create_tables`` from the backend directory.
"""

from scripts import create_tables


if __name__ == "__main__":
    create_tables.main()
