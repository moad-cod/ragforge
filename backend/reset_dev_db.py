import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
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
        check_compatibility=False,
    )
    collections = client.get_collections().collections
    for collection in collections:
        client.delete_collection(collection_name=collection.name)
    return len(collections)


async def drop_application_tables() -> None:
    async with engine.begin() as conn:
        # drop_all() cannot reset a legacy schema when an out-of-line foreign
        # key exists in current metadata but not in the database. Drop the
        # application tables together so PostgreSQL resolves either version of
        # the dependency graph; Alembic then recreates the current schema.
        preparer = conn.dialect.identifier_preparer
        names = [*sorted(Base.metadata.tables), "alembic_version"]
        table_names = ", ".join(preparer.quote(table_name) for table_name in names)
        await conn.execute(text(f"DROP TABLE IF EXISTS {table_names} CASCADE"))


def migrate_to_head() -> None:
    backend_dir = Path(__file__).resolve().parent
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(config, "head")


async def main():
    print("Resetting RAGForge development state...")
    deleted_collections = reset_qdrant()
    print(f"Deleted {deleted_collections} Qdrant collection(s)")

    await drop_application_tables()
    await engine.dispose()
    print("Dropped all application database tables")


if __name__ == "__main__":
    asyncio.run(main())
    migrate_to_head()
    print("Recreated the database at the latest Alembic revision")
    print("Fresh development reset complete. You can run test_chunkers.sh again.")
