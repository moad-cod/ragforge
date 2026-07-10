from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.db import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    current_version_id = Column(UUID(as_uuid=False), nullable=True)
    source_type = Column(String, nullable=True)
    filename = Column(String, nullable=True)
    mime_type = Column(String, nullable=True)
    extension = Column(String, nullable=True)
    status = Column(String, nullable=False, default="uploaded")
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="documents")
    creator = relationship("User", foreign_keys=[created_by])
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")

    @property
    def source(self) -> str | None:
        return self.source_type

    @source.setter
    def source(self, value: str | None) -> None:
        self.source_type = value

    @property
    def collection(self) -> str | None:
        return self.project.collection if self.project else None

    __table_args__ = (
        Index("ix_documents_project_id", "project_id"),
        Index("ix_documents_current_version_id", "current_version_id"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_created_by", "created_by"),
        Index("ix_documents_created_at", "created_at"),
        Index("ix_documents_deleted_at", "deleted_at"),
    )
