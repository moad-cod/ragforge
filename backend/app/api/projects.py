from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.tables import Project, Document, Organization
from app.repositories import projects as project_repository
from app.services.indexer import delete_document_chunks, delete_collection
from pydantic import BaseModel, field_validator
from datetime import datetime
import uuid
import asyncio

router = APIRouter()

class ProjectCreate(BaseModel):
    name: str
    organization_id: str | None = None

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

class ProjectResponse(BaseModel):
    project_id: str
    organization_id: str | None
    name: str
    collection: str
    qdrant_collection: str
    created_by: str
    created_at: datetime
    updated_at: datetime


def _project_payload(project: Project) -> ProjectResponse:
    return ProjectResponse(
        project_id=project.id,
        organization_id=project.organization_id,
        name=project.name,
        collection=project.collection,
        qdrant_collection=project.qdrant_collection,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("/", response_model=ProjectResponse)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if body.organization_id:
        org_result = await db.execute(
            select(Organization).where(
                Organization.id == body.organization_id,
                Organization.deleted_at.is_(None),
            )
        )
        if not org_result.scalar_one_or_none():
            raise HTTPException(400, "Organization not found")

    project_id = str(uuid.uuid4())
    collection = f"project_{project_id}"
    project = await project_repository.create_project(
        db,
        id=project_id,
        organization_id=body.organization_id,
        created_by=user["user_id"],
        name=body.name,
        qdrant_collection=collection,
    )
    await db.commit()
    await db.refresh(project)
    return _project_payload(project)


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    projects = await project_repository.list_user_projects(db, user["user_id"])
    return [_project_payload(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    project = await project_repository.get_owned_project(db, project_id, user["user_id"])
    if not project:
        raise HTTPException(404, "Project not found")
    return _project_payload(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    project = await project_repository.rename_project(db, project_id, user["user_id"], body.name)
    if not project:
        raise HTTPException(404, "Project not found")

    # only update display name — collection name stays the same
    # changing collection would require re-indexing all documents
    await db.commit()
    await db.refresh(project)

    return _project_payload(project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    project = await project_repository.get_owned_project(db, project_id, user["user_id"])
    if not project:
        raise HTTPException(404, "Project not found")

    docs_result = await db.execute(
        select(Document).where(
            Document.project_id == project_id,
            Document.deleted_at.is_(None),
        )
    )
    docs = docs_result.scalars().all()
    for doc in docs:
        await asyncio.to_thread(delete_document_chunks, document_id=doc.id, collection=project.collection)
        if doc.source_type == "multimodal":
            from app.services.storage import delete_document_images
            try:
                await asyncio.to_thread(delete_document_images, doc.id)
            except Exception:
                pass
        doc.status = "deleted"
        doc.deleted_at = datetime.utcnow()

    await asyncio.to_thread(delete_collection, project.collection)
    await asyncio.to_thread(delete_collection, f"{project.collection}_multimodal")

    project.deleted_at = datetime.utcnow()
    await db.commit()

    return {
        "deleted_project": project_id,
        "deleted_collection": project.collection,
        "deleted_documents": len(docs),
    }
