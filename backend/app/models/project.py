from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.db import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=True)
    name = Column(String, nullable=False)
    qdrant_collection = Column(String, unique=True, nullable=False)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="projects")
    creator = relationship("User", back_populates="projects", foreign_keys=[created_by])
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")

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
