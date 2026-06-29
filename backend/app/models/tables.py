from sqlalchemy import Column, String, DateTime, ForeignKey
from app.core.db import Base
from datetime import datetime
import uuid

class User(Base):
    __tablename__ = "users"
    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email           = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow)

class Project(Base):
    __tablename__ = "projects"
    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = Column(String, ForeignKey("users.id"), nullable=False)
    name       = Column(String, nullable=False)
    collection = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Document(Base):
    __tablename__ = "documents"
    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    filename   = Column(String)
    source     = Column(String)
    chunks     = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)