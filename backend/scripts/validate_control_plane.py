"""Validate the migrated RAGForge control-plane database schema."""

import asyncio

try:
    from scripts._bootstrap import ensure_backend_path
except ModuleNotFoundError:
    try:
        from backend.scripts._bootstrap import ensure_backend_path
    except ModuleNotFoundError:
        from _bootstrap import ensure_backend_path

ensure_backend_path()

from app.core.db import engine
from app.services.control_plane_validation import validate_control_plane_schema


async def validate() -> int:
    report = await validate_control_plane_schema(engine)
    for name, passed in report.checks.items():
        marker = "PASS" if passed else "FAIL"
        print(f"[{marker}] {name}")
        if not passed:
            for missing in report.missing[name]:
                print(f"  missing: {missing}")
    await engine.dispose()
    return 0 if report.ok else 1


def main() -> int:
    return asyncio.run(validate())


if __name__ == "__main__":
    raise SystemExit(main())
