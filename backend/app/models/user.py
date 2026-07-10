from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=True)
    email = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="users")
    projects = relationship("Project", back_populates="creator", foreign_keys="Project.created_by")

    __table_args__ = (
        Index("ix_users_organization_id", "organization_id"),
        Index("ix_users_deleted_at", "deleted_at"),
    )
