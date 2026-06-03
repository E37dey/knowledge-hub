"""Pydantic request/response schemas for the HTTP layer.

Deliberately separate from ORM models so:
  * `hashed_password` is never serialised out of an endpoint.
  * `user_id` is never accepted from the client — it's always derived
    from the JWT (see app/auth/deps.py).
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Auth -----------------------------------------------------------------

class UserRegister(BaseModel):
    email: EmailStr
    # Minimum length is a coarse defence — better than nothing without
    # enforcing a brittle character-class policy. Bcrypt happily hashes
    # the rest; the hard limit guards against pathological inputs.
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    """User data safe to return to a client. Excludes hashed_password."""
    id: UUID
    email: EmailStr
    created_at: datetime

    # Lets FastAPI / response_model build this from a SQLAlchemy User
    # row directly, without a manual to-dict step.
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


# --- Documents ------------------------------------------------------------

class DocumentPublic(BaseModel):
    """A document row as returned to its owner.

    `user_id` is intentionally absent — the client only ever sees its
    own documents (the endpoint filters by the JWT user), so echoing the
    owner id back would be redundant noise.
    """
    id: UUID
    filename: str
    # status ∈ { "processing", "indexed", "failed" }
    status: str
    chunk_count: int
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Query ----------------------------------------------------------------

class Source(BaseModel):
    """One retrieved chunk shown to the model and surfaced to the user.

    Mirrors the dict shape returned by the vector store / retrieval layer,
    so a chunk can be validated into a Source with no manual mapping —
    both on the live response and when re-hydrating from the JSONB column
    in query history.
    """
    filename: str
    page: int
    chunk_index: int
    document_id: UUID
    score: float
    text: str


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    # Bounded so a client can't request an unreasonably large context
    # window (which would bloat the prompt and the stored sources blob).
    top_k: int = Field(default=5, ge=1, le=20)


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]
    response_time_ms: int


class QueryHistoryItem(BaseModel):
    """A past query as returned from /query/history."""
    id: UUID
    question: str
    answer: str
    sources: list[Source]
    response_time_ms: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
