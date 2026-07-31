import asyncio
try:
    from scripts._bootstrap import ensure_backend_path
except ModuleNotFoundError:
    try:
        from backend.scripts._bootstrap import ensure_backend_path
    except ModuleNotFoundError:
        from _bootstrap import ensure_backend_path

ensure_backend_path()

from app.core.db import engine, Base
from app.models.tables import (
    Chunk,
    Document,
    DocumentVersion,
    EmbeddingRun,
    IngestionRun,
    Organization,
    Project,
    QueryLog,
    RetrievalLog,
    User,
)

async def create_missing_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Missing tables created")


def main() -> None:
    asyncio.run(create_missing_tables())


if __name__ == "__main__":
    main()
