"""SQLAlchemy ORM models: User, Document, Query.

Every row in `documents` and `queries` is anchored to a `user_id` —
the foundation of per-user data isolation in the relational layer.
The vector store (app/rag/vectorstore.py) enforces the same isolation
via payload filters.

Cascade strategy (three layers, by design):
  1. DB-side ON DELETE CASCADE on the FK — catches direct SQL deletes.
  2. ORM-side cascade="all, delete-orphan" on the relationship — keeps
     the in-memory object graph consistent.
  3. passive_deletes=True — tells SQLAlchemy to trust the DB cascade
     rather than emit a SELECT + per-row DELETE in Python.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


def _utcnow() -> datetime:
    """Default factory for created_at / uploaded_at columns.

    Defined as a callable, not `datetime.now(timezone.utc)` directly,
    so each row gets its own timestamp instead of a value frozen at
    module import time.
    """
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    documents = relationship(
        "Document",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    queries = relationship(
        "Query",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename = Column(String, nullable=False)
    # status ∈ { "processing", "indexed", "failed" }
    status = Column(String, nullable=False, default="processing")
    chunk_count = Column(Integer, nullable=False, default=0)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    user = relationship("User", back_populates="documents")


class Query(Base):
    __tablename__ = "queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question = Column(String, nullable=False)
    answer = Column(String, nullable=False)
    # JSONB (not plain JSON) for queryable indexes on source fields later.
    sources = Column(JSONB, nullable=False, default=list)
    response_time_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    user = relationship("User", back_populates="queries")
