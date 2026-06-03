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


# --- Documents (task 4) ---------------------------------------------------
# TODO: DocumentPublic — id, filename, status, chunk_count, uploaded_at


# --- Query (task 5) -------------------------------------------------------
# TODO: Source — filename, page, chunk_index, score, text
# TODO: QueryRequest, QueryResponse, QueryHistoryItem
