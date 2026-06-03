"""Query endpoints: ask a question + browse history. Per-user.

Isolation contract:
  * Ask     -> retrieval is filtered to current_user.id BEFORE Claude
               sees anything (the filter lives in the vector store). A
               user's question can never be answered with — or cite —
               chunks belonging to another user.
  * History -> only the current user's past Query rows are returned.

Persistence: each answered question is written to the `queries` table
with its sources (JSONB) and measured latency, so the dashboard can show
a per-user history. `user_id` always comes from the JWT, never the body.
"""
from time import perf_counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Query, User
from app.schemas import QueryHistoryItem, QueryRequest, QueryResponse
from app.services import rag as rag_service

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
def ask(
    payload: QueryRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QueryResponse:
    """Answer a question from the user's own corpus and record it.

    Latency is measured around the full RAG round-trip (retrieval +
    Claude) so the stored `response_time_ms` reflects what the user
    actually waited for.
    """
    started = perf_counter()
    result = rag_service.query(
        user_id=str(user.id),
        question=payload.question,
        top_k=payload.top_k,
    )
    elapsed_ms = int((perf_counter() - started) * 1000)

    row = Query(
        user_id=user.id,
        question=payload.question,
        answer=result["answer"],
        sources=result["sources"],
        response_time_ms=elapsed_ms,
    )
    db.add(row)
    db.commit()

    return QueryResponse(
        answer=result["answer"],
        sources=result["sources"],
        response_time_ms=elapsed_ms,
    )


@router.get("/history", response_model=list[QueryHistoryItem])
def history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Query]:
    """Return the current user's most recent queries, newest first.

    Capped at 50 — enough for a dashboard panel without unbounded
    payloads as a user's history grows.
    """
    return (
        db.query(Query)
        .filter(Query.user_id == user.id)
        .order_by(Query.created_at.desc())
        .limit(50)
        .all()
    )
