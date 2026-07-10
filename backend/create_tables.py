import asyncio
from app.core.db import engine, Base
from app.models.tables import Organization, User, Project, Document, DocumentVersion

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Missing tables created")

asyncio.run(main())
