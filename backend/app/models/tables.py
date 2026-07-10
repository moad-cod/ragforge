from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.db import Base
from datetime import datetime
import uuid

class Organization(Base):
    __tablename__ = "organizations"

    id         = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    name       = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    users = relationship("User", back_populates="organization")
    projects = relationship("Project", back_populates="organization")

class User(Base):
    __tablename__ = "users"
    id              = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=True)
    email           = Column(String, unique=True, nullable=False)
    full_name       = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at      = Column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="users")
    projects = relationship("Project", back_populates="creator", foreign_keys="Project.created_by")

    __table_args__ = (
        Index("ix_users_organization_id", "organization_id"),
        Index("ix_users_deleted_at", "deleted_at"),
    )

class Project(Base):
    __tablename__ = "projects"
    id                = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id   = Column(UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=True)
    name              = Column(String, nullable=False)
    qdrant_collection = Column(String, unique=True, nullable=False)
    created_by        = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at        = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at        = Column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="projects")
    creator      = relationship("User", back_populates="projects", foreign_keys=[created_by])
    documents    = relationship("Document", back_populates="project", cascade="all, delete-orphan")

    @property
    def collection(self) -> str:
        return self.qdrant_collection

    @collection.setter
    def collection(self, value: str) -> None:
        self.qdrant_collection = value

    __table_args__ = (
        Index("ix_projects_organization_id", "organization_id"),
        Index("ix_projects_created_by", "created_by"),
        Index("ix_projects_created_at", "created_at"),
        Index("ix_projects_deleted_at", "deleted_at"),
    )

class Document(Base):
    __tablename__ = "documents"
    id         = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename   = Column(String)
    source     = Column(String)
    chunks     = Column(String)
    collection = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="documents")

    __table_args__ = (
        Index("ix_documents_project_id", "project_id"),
        Index("ix_documents_collection", "collection"),
    )
