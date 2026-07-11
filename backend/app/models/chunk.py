from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.db import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    document_version_id = Column(
        UUID(as_uuid=False), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )
    ingestion_run_id = Column(
        UUID(as_uuid=False), ForeignKey("ingestion_runs.id", ondelete="SET NULL"), nullable=True
    )
    qdrant_point_id = Column(String, unique=True, nullable=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    content_hash = Column(String, nullable=False)
    token_count = Column(Integer, nullable=True)
    page_start = Column(Integer, nullable=True)
    page_end = Column(Integer, nullable=True)
    section_title = Column(String, nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="chunks")
    document = relationship("Document", back_populates="chunks")
    document_version = relationship("DocumentVersion", back_populates="chunks")
    ingestion_run = relationship("IngestionRun", back_populates="chunks")
    retrieval_logs = relationship("RetrievalLog", back_populates="chunk")

    __table_args__ = (
        UniqueConstraint("document_version_id", "chunk_index", name="uq_chunks_version_chunk_index"),
        UniqueConstraint("document_version_id", "content_hash", name="uq_chunks_version_content_hash"),
        Index("ix_chunks_project_id", "project_id"),
        Index("ix_chunks_document_id", "document_id"),
        Index("ix_chunks_document_version_id", "document_version_id"),
        Index("ix_chunks_ingestion_run_id", "ingestion_run_id"),
        Index("ix_chunks_qdrant_point_id", "qdrant_point_id"),
        Index("ix_chunks_content_hash", "content_hash"),
        Index("ix_chunks_created_at", "created_at"),
        Index("ix_chunks_project_document", "project_id", "document_id"),
        Index("ix_chunks_version_chunk_index", "document_version_id", "chunk_index"),
    )
