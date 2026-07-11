from datetime import datetime
import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates

from app.core.db import Base
from app.models.statuses import INGESTION_RUN_STATUSES, status_check_sql, validate_status


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    document_version_id = Column(
        UUID(as_uuid=False), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )
    status = Column(String, nullable=False, default="queued")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)
    airflow_dag_run_id = Column(String, nullable=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="ingestion_runs")
    document = relationship("Document", back_populates="ingestion_runs")
    document_version = relationship("DocumentVersion", back_populates="ingestion_runs")
    creator = relationship("User", back_populates="ingestion_runs")
    chunks = relationship("Chunk", back_populates="ingestion_run")

    @validates("status")
    def validate_status(self, _key: str, value: str) -> str:
        return validate_status(value, INGESTION_RUN_STATUSES, "ingestion run status")

    __table_args__ = (
        CheckConstraint(
            status_check_sql("status", INGESTION_RUN_STATUSES),
            name="ck_ingestion_runs_status",
        ),
        Index("ix_ingestion_runs_project_id", "project_id"),
        Index("ix_ingestion_runs_document_id", "document_id"),
        Index("ix_ingestion_runs_document_version_id", "document_version_id"),
        Index("ix_ingestion_runs_status", "status"),
        Index("ix_ingestion_runs_created_at", "created_at"),
        Index("ix_ingestion_runs_airflow_dag_run_id", "airflow_dag_run_id"),
    )
