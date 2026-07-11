from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.db import Base


class RetrievalLog(Base):
    __tablename__ = "retrieval_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_log_id = Column(
        UUID(as_uuid=False), ForeignKey("query_logs.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id = Column(UUID(as_uuid=False), ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True)
    qdrant_score = Column(Float, nullable=True)
    rerank_score = Column(Float, nullable=True)
    rank = Column(Integer, nullable=False)
    retrieval_strategy = Column(String, nullable=True)
    used_in_answer = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    query_log = relationship("QueryLog", back_populates="retrieval_logs")
    chunk = relationship("Chunk", back_populates="retrieval_logs")

    __table_args__ = (
        Index("ix_retrieval_logs_query_log_id", "query_log_id"),
        Index("ix_retrieval_logs_chunk_id", "chunk_id"),
        Index("ix_retrieval_logs_rank", "rank"),
        Index("ix_retrieval_logs_query_rank", "query_log_id", "rank"),
    )
