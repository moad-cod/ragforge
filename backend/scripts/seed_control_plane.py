"""Create deterministic development data for the RAGForge control plane."""

import argparse
import asyncio

try:
    from scripts._bootstrap import ensure_backend_path
except ModuleNotFoundError:
    try:
        from backend.scripts._bootstrap import ensure_backend_path
    except ModuleNotFoundError:
        from _bootstrap import ensure_backend_path

ensure_backend_path()

from app.core.db import AsyncSessionLocal
from app.services.control_plane_seed import seed_control_plane


async def seed(namespace: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await seed_control_plane(db, namespace=namespace)
        await db.commit()

    print(f"Seeded control-plane namespace: {namespace}")
    for field, value in vars(result).items():
        print(f"{field}={value}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--namespace",
        default="development",
        help="Stable namespace used to derive repeatable IDs (default: development)",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.namespace))


if __name__ == "__main__":
    main()
