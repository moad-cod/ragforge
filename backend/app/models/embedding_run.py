from datetime import datetime
import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates

from app.core.db import Base
from app.models.statuses import EMBEDDING_RUN_STATUSES, status_check_sql, validate_status


class EmbeddingRun(Base):
    __tablename__ = "embedding_runs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    document_version_id = Column(
        UUID(as_uuid=False), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )
    embedding_model = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")
    total_chunks = Column(Integer, nullable=False, default=0)
    embedded_chunks = Column(Integer, nullable=False, default=0)
    total_batches = Column(Integer, nullable=False, default=0)
    embedded_batches = Column(Integer, nullable=False, default=0)
    batch_size = Column(Integer, nullable=True)
    embedding_backend = Column(String, nullable=True)
    embedding_device = Column(String, nullable=True)
    embedding_dimension = Column(Integer, nullable=True)
    attempt = Column(Integer, nullable=False, default=1)
    started_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    last_heartbeat_at = Column(DateTime, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="embedding_runs")
    document_version = relationship("DocumentVersion", back_populates="embedding_runs")

    @validates("status")
    def validate_status(self, _key: str, value: str) -> str:
        return validate_status(value, EMBEDDING_RUN_STATUSES, "embedding run status")

    __table_args__ = (
        CheckConstraint(
            status_check_sql("status", EMBEDDING_RUN_STATUSES),
            name="ck_embedding_runs_status",
        ),
        UniqueConstraint(
            "document_version_id",
            "embedding_model",
            name="uq_embedding_runs_version_model",
        ),
        Index("ix_embedding_runs_project_id", "project_id"),
        Index("ix_embedding_runs_document_version_id", "document_version_id"),
        Index("ix_embedding_runs_embedding_model", "embedding_model"),
        Index("ix_embedding_runs_status", "status"),
        Index("ix_embedding_runs_created_at", "created_at"),
    )
