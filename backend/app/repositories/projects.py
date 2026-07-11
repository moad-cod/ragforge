from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project


async def create_project(db: AsyncSession, **values) -> Project:
    project = Project(**values)
    db.add(project)
    await db.flush()
    return project


async def get_project(db: AsyncSession, project_id: str) -> Project | None:
    return await db.get(Project, project_id)


async def get_owned_project(db: AsyncSession, project_id: str, user_id: str) -> Project | None:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.created_by == user_id,
            Project.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def list_user_projects(db: AsyncSession, user_id: str) -> list[Project]:
    result = await db.execute(
        select(Project)
        .where(Project.created_by == user_id, Project.deleted_at.is_(None))
        .order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def rename_project(db: AsyncSession, project_id: str, user_id: str, name: str) -> Project | None:
    project = await get_owned_project(db, project_id, user_id)
    if project is not None:
        project.name = name
        await db.flush()
    return project
