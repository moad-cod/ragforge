from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt
from app.core.config import settings
from app.core.db import get_db
from app.models.tables import User, Project, Document, Organization
from app.core.auth import get_current_user
from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict, field_validator
import uuid
import bcrypt

router = APIRouter()


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "strong-password",
                "full_name": "Example User",
            }
        }
    )

    email: str
    password: str
    full_name: str | None = None
    organization_id: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or "." not in normalized.rsplit("@", 1)[-1]:
            raise ValueError("Invalid email address")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value

    @field_validator("organization_id")
    @classmethod
    def validate_organization_id(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        try:
            return str(uuid.UUID(value.strip()))
        except ValueError as exc:
            raise ValueError("organization_id must be a valid UUID") from exc

class UpdateMeRequest(BaseModel):
    email: str | None = None
    password: str | None = None
    full_name: str | None = None
    organization_id: str | None = None

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if "@" not in normalized or "." not in normalized.rsplit("@", 1)[-1]:
            raise ValueError("Invalid email address")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_optional_password(cls, value: str | None) -> str | None:
        if value is not None and len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value

    @field_validator("organization_id")
    @classmethod
    def validate_optional_organization_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return ""
        try:
            return str(uuid.UUID(normalized))
        except ValueError as exc:
            raise ValueError("organization_id must be a valid UUID") from exc

class UserResponse(BaseModel):
    user_id: str
    organization_id: str | None
    email: str
    full_name: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


def _user_payload(user: User) -> UserResponse:
    return UserResponse(
        user_id=user.id,
        organization_id=user.organization_id,
        email=user.email,
        full_name=user.full_name,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.email == body.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")
    if body.organization_id:
        org_result = await db.execute(
            select(Organization).where(
                Organization.id == body.organization_id,
                Organization.deleted_at.is_(None),
            )
        )
        if not org_result.scalar_one_or_none():
            raise HTTPException(400, "Organization not found")

    user = User(
        id=str(uuid.uuid4()),
        organization_id=body.organization_id,
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _user_payload(user)


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.email == form.username, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")

    token = jwt.encode(
        {"sub": user.id, "exp": datetime.utcnow() + timedelta(days=7)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    return {"access_token": token, "token_type": "bearer"}


# ── Get current user ──────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(User).where(User.id == user["user_id"], User.deleted_at.is_(None))
    )
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(404, "User not found")
    return _user_payload(u)


# ── Update current user ───────────────────────────────────────────────────────

@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UpdateMeRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(User).where(User.id == user["user_id"], User.deleted_at.is_(None))
    )
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(404, "User not found")

    if body.email:
        # check email not taken by another user
        existing = await db.execute(
            select(User).where(
                User.email == body.email,
                User.id != user["user_id"],
                User.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(400, "Email already in use")
        u.email = body.email

    if body.password:
        u.hashed_password = hash_password(body.password)
    if body.full_name is not None:
        u.full_name = body.full_name
    if body.organization_id is not None:
        if body.organization_id:
            org_result = await db.execute(
                select(Organization).where(
                    Organization.id == body.organization_id,
                    Organization.deleted_at.is_(None),
                )
            )
            if not org_result.scalar_one_or_none():
                raise HTTPException(400, "Organization not found")
        u.organization_id = body.organization_id or None

    await db.commit()
    await db.refresh(u)
    return _user_payload(u)


# ── Delete current user ───────────────────────────────────────────────────────

@router.delete("/me")
async def delete_me(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(User).where(User.id == user["user_id"], User.deleted_at.is_(None))
    )
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(404, "User not found")

    # delete all Qdrant collections for this user's projects
    from app.services.indexer import delete_collection
    projects_result = await db.execute(
        select(Project).where(
            Project.created_by == user["user_id"],
            Project.deleted_at.is_(None),
        )
    )
    projects = projects_result.scalars().all()
    for project in projects:
        delete_collection(project.collection)
        delete_collection(f"{project.collection}_multimodal")
        project.deleted_at = datetime.utcnow()

    u.deleted_at = datetime.utcnow()
    await db.commit()

    return {
        "deleted_user": user["user_id"],
        "deleted_projects": len(projects),
    }
