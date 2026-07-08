from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt
from app.core.config import settings
from app.core.db import get_db
from app.models.tables import User, Project, Document
from app.core.auth import get_current_user
from datetime import datetime, timedelta
from pydantic import BaseModel
from pydantic import field_validator
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
    email: str
    password: str

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

class UpdateMeRequest(BaseModel):
    email: str | None = None
    password: str | None = None

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


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    return {"user_id": user.id, "email": user.email}


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == form.username))
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

@router.get("/me")
async def get_me(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user["user_id"]))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(404, "User not found")
    return {"user_id": u.id, "email": u.email, "created_at": u.created_at}


# ── Update current user ───────────────────────────────────────────────────────

@router.patch("/me")
async def update_me(
    body: UpdateMeRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user["user_id"]))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(404, "User not found")

    if body.email:
        # check email not taken by another user
        existing = await db.execute(
            select(User).where(User.email == body.email, User.id != user["user_id"])
        )
        if existing.scalar_one_or_none():
            raise HTTPException(400, "Email already in use")
        u.email = body.email

    if body.password:
        u.hashed_password = hash_password(body.password)

    await db.commit()
    return {"user_id": u.id, "email": u.email}


# ── Delete current user ───────────────────────────────────────────────────────

@router.delete("/me")
async def delete_me(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user["user_id"]))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(404, "User not found")

    # delete all Qdrant collections for this user's projects
    from app.services.indexer import delete_collection
    projects_result = await db.execute(
        select(Project).where(Project.user_id == user["user_id"])
    )
    projects = projects_result.scalars().all()
    for project in projects:
        delete_collection(project.collection)

    # delete user — cascades to projects → documents in postgres
    await db.delete(u)
    await db.commit()

    return {
        "deleted_user": user["user_id"],
        "deleted_projects": len(projects),
    }
