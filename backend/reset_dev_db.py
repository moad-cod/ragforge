import asyncio
from sqlalchemy import text

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
from app.core.config import settings
from qdrant_client import QdrantClient


def reset_qdrant() -> int:
    client = QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
    )
    collections = client.get_collections().collections
    for collection in collections:
        client.delete_collection(collection_name=collection.name)
    return len(collections)


async def rebuild_tables() -> None:
    async with engine.begin() as conn:
        # drop_all() cannot reset a legacy schema when an out-of-line foreign
        # key exists in current metadata but not in the database. Drop the
        # application tables together so PostgreSQL resolves either version of
        # the dependency graph, then recreate the current schema from metadata.
        preparer = conn.dialect.identifier_preparer
        table_names = ", ".join(
            preparer.quote(table_name)
            for table_name in sorted(Base.metadata.tables)
        )
        await conn.execute(text(f"DROP TABLE IF EXISTS {table_names} CASCADE"))
        await conn.run_sync(Base.metadata.create_all)


async def main():
    print("Resetting RAGForge development state...")
    deleted_collections = reset_qdrant()
    print(f"Deleted {deleted_collections} Qdrant collection(s)")

    await rebuild_tables()
    await engine.dispose()
    print("Dropped and recreated all database tables")
    print("Fresh development reset complete. You can run test_chunkers.sh again.")


if __name__ == "__main__":
    asyncio.run(main())
