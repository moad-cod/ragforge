from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.tables import Project, Document
from app.services.indexer import delete_document_chunks, delete_collection
from pydantic import BaseModel, field_validator
import uuid
import asyncio

router = APIRouter()

class ProjectCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Project name is required")
        if len(name) > 120:
            raise ValueError("Project name must be 120 characters or fewer")
        return name

class ProjectUpdate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return ProjectCreate.validate_name(value)


@router.post("/")
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    project_id = str(uuid.uuid4())
    collection = f"project_{project_id.replace('-', '_')}"
    project = Project(
        id=project_id,
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
        await asyncio.to_thread(delete_document_chunks, document_id=doc.id, collection=doc.collection)
        if doc.source == "multimodal":
            from app.services.storage import delete_document_images
            try:
                await asyncio.to_thread(delete_document_images, doc.id)
            except Exception:
                pass

    await asyncio.to_thread(delete_collection, project.collection)
    await asyncio.to_thread(delete_collection, f"{project.collection}_multimodal")

    await db.delete(project)
    await db.commit()

    return {
        "deleted_project": project_id,
        "deleted_collection": project.collection,
        "deleted_documents": len(docs),
    }
