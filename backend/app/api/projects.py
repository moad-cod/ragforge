from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.tables import Project, Document
from app.services.indexer import delete_document_chunks, delete_collection
from pydantic import BaseModel
import uuid

router = APIRouter()

class ProjectCreate(BaseModel):
    name: str

class ProjectUpdate(BaseModel):
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
    return [
        {"project_id": p.id, "name": p.name, "collection": p.collection, "created_at": p.created_at}
        for p in projects
    ]


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
    return {"project_id": project.id, "name": project.name, "collection": project.collection, "created_at": project.created_at}


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user["user_id"])
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")

    # only update display name — collection name stays the same
    # changing collection would require re-indexing all documents
    project.name = body.name
    await db.commit()

    return {"project_id": project.id, "name": project.name, "collection": project.collection}


@router.delete("/{project_id}")
async def delete_project(
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

    docs_result = await db.execute(
        select(Document).where(Document.project_id == project_id)
    )
    docs = docs_result.scalars().all()
    for doc in docs:
        delete_document_chunks(document_id=doc.id, collection=project.collection)

    delete_collection(project.collection)

    await db.delete(project)
    await db.commit()

    return {
        "deleted_project": project_id,
        "deleted_collection": project.collection,
        "deleted_documents": len(docs),
    }