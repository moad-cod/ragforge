from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.db import Base


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    normalized_question_hash = Column(String, nullable=True)
    provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    cache_hit = Column(Boolean, nullable=False, default=False)
    route = Column(String, nullable=True)
    relevance_score = Column(Float, nullable=True)
    groundedness_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="query_logs")
    user = relationship("User", back_populates="query_logs")
    retrieval_logs = relationship(
        "RetrievalLog",
        back_populates="query_log",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_query_logs_project_id", "project_id"),
        Index("ix_query_logs_user_id", "user_id"),
        Index("ix_query_logs_normalized_question_hash", "normalized_question_hash"),
        Index("ix_query_logs_created_at", "created_at"),
        Index("ix_query_logs_project_created_at", "project_id", "created_at"),
    )
