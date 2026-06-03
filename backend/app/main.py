"""FastAPI application entry point.

Run: py -m uvicorn app.main:app --port 8000 --reload   (from backend/)
Docs: http://localhost:8000/docs
"""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.deps import get_current_user
from app.auth.routes import router as auth_router
from app.config import settings
from app.documents.routes import router as documents_router
from app.models import User
from app.query.routes import router as query_router
from app.schemas import UserPublic

app = FastAPI(
    title="Knowledge Hub",
    description=(
        "Multi-user RAG platform. Users register, upload their own "
        "documents, and ask grounded questions against their personal "
        "corpus. Data is isolated per-user in both Postgres and Qdrant."
    ),
    version="0.1.0",
)

# In production the frontend is served from a different origin than the API,
# so the browser needs an explicit CORS allowance. Origins come from
# CORS_ORIGINS (comma-separated) — in dev the Vite proxy makes this a no-op.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/me", response_model=UserPublic, tags=["auth"])
def read_current_user(user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user. Useful for verifying a token from
    the frontend and as a smoke test of the auth dependency."""
    return user


app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(query_router)
