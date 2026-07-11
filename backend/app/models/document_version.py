from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.db import Base


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    content_hash = Column(String, nullable=False)
    bronze_path = Column(String, nullable=True)
    silver_path = Column(String, nullable=True)
    gold_path = Column(String, nullable=True)
    parser_name = Column(String, nullable=True)
    chunker_id = Column(String, nullable=True)
    embedding_model = Column(String, nullable=True)
    status = Column(String, nullable=False)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="versions", foreign_keys=[document_id])
    ingestion_runs = relationship("IngestionRun", back_populates="document_version")
    chunks = relationship("Chunk", back_populates="document_version")
    embedding_runs = relationship("EmbeddingRun", back_populates="document_version")

    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_versions_document_version_number"),
        UniqueConstraint("document_id", "content_hash", name="uq_document_versions_document_content_hash"),
        Index("ix_document_versions_document_id", "document_id"),
        Index("ix_document_versions_status", "status"),
        Index("ix_document_versions_content_hash", "content_hash"),
        Index("ix_document_versions_created_at", "created_at"),
    )
