import asyncio
from app.core.db import engine, Base
from app.models.tables import User, Project, Document

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables recreated")

asyncio.run(main())