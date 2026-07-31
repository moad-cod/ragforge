"""Compatibility wrapper for ``python check_data.py``.

Prefer ``python -m scripts.check_data`` from the backend directory.
"""

from scripts import check_data


if __name__ == "__main__":
    check_data.main()
