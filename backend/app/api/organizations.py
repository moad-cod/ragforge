from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.tables import Organization

router = APIRouter()


class OrganizationCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Organization name is required")
        if len(name) > 160:
            raise ValueError("Organization name must be 160 characters or fewer")
        return name


class OrganizationUpdate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return OrganizationCreate.validate_name(value)


class OrganizationResponse(BaseModel):
    organization_id: str
    name: str
    created_at: datetime
    updated_at: datetime


def _organization_payload(organization: Organization) -> OrganizationResponse:
    return OrganizationResponse(
        organization_id=organization.id,
        name=organization.name,
        created_at=organization.created_at,
        updated_at=organization.updated_at,
    )


@router.post("/", response_model=OrganizationResponse)
async def create_organization(
    body: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    organization = Organization(name=body.name)
    db.add(organization)
    await db.commit()
    await db.refresh(organization)
    return _organization_payload(organization)


@router.get("/", response_model=list[OrganizationResponse])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Organization).where(Organization.deleted_at.is_(None))
    )
    return [_organization_payload(org) for org in result.scalars().all()]


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.deleted_at.is_(None),
        )
    )
    organization = result.scalar_one_or_none()
    if not organization:
        raise HTTPException(404, "Organization not found")
    return _organization_payload(organization)


@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: str,
    body: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.deleted_at.is_(None),
        )
    )
    organization = result.scalar_one_or_none()
    if not organization:
        raise HTTPException(404, "Organization not found")

    organization.name = body.name
    await db.commit()
    await db.refresh(organization)
    return _organization_payload(organization)


@router.delete("/{organization_id}")
async def delete_organization(
    organization_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.deleted_at.is_(None),
        )
    )
    organization = result.scalar_one_or_none()
    if not organization:
        raise HTTPException(404, "Organization not found")

    organization.deleted_at = datetime.utcnow()
    await db.commit()
    return {"deleted_organization": organization_id}
