from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.tables import Project
from pydantic import BaseModel
import uuid

router = APIRouter()

class ProjectCreate(BaseModel):
    name: str

@router.post("/")
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    collection = body.name.strip().lower().replace(" ", "_")
    project = Project(
        id=str(uuid.uuid4()),
        user_id=user["user_id"],
        name=body.name,
        collection=collection,
    )
    db.add(project)
    await db.commit()
    return {"project_id": project.id, "name": project.name, "collection": collection}

@router.get("/")
async def list_projects(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Project).where(Project.user_id == user["user_id"])
    )
    projects = result.scalars().all()
    return [{"project_id": p.id, "name": p.name, "collection": p.collection} for p in projects]

@router.get("/{project_id}")
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user["user_id"])
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    return {"project_id": project.id, "name": project.name, "collection": project.collection}