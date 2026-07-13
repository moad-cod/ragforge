from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RetrievalLog


async def bulk_insert_retrieval_logs(
    db: AsyncSession,
    retrieval_logs: list[RetrievalLog | dict],
) -> list[RetrievalLog]:
    records = [
        log if isinstance(log, RetrievalLog) else RetrievalLog(**log)
        for log in retrieval_logs
    ]
    db.add_all(records)
    await db.flush()
    return records


async def get_retrieval_logs_for_query(db: AsyncSession, query_log_id: str) -> list[RetrievalLog]:
    result = await db.execute(
        select(RetrievalLog)
        .where(RetrievalLog.query_log_id == query_log_id)
        .order_by(RetrievalLog.rank)
    )
    return list(result.scalars().all())


async def mark_retrieval_logs_used(
    db: AsyncSession,
    retrieval_logs: list[RetrievalLog],
) -> None:
    for retrieval_log in retrieval_logs:
        retrieval_log.used_in_answer = True
    await db.flush()
