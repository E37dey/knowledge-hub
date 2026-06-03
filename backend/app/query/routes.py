"""Query endpoints: ask a question + browse history. Per-user.

Isolation contract:
  * Ask     -> retrieval filtered to current_user.id BEFORE Claude sees
               anything. The user's question can never be answered with
               chunks belonging to another user.
  * History -> only the current user's past Query rows.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/query", tags=["query"])


# TODO: @router.post("/", response_model=QueryResponse)
#       def ask(
#           payload: QueryRequest,
#           user: User = Depends(get_current_user),
#           db: Session = Depends(get_db),
#       ):
#           - t0 = perf_counter()
#           - chunks = retrieve(payload.question, user_id=user.id, top_k=payload.top_k)
#           - result = generate_answer(payload.question, chunks)
#           - elapsed_ms = int((perf_counter() - t0) * 1000)
#           - persist Query row (user_id, question, answer, sources, elapsed_ms)
#           - return QueryResponse(answer, sources, response_time_ms=elapsed_ms)


# TODO: @router.get("/history", response_model=list[QueryHistoryItem])
#       def history(user = Depends(get_current_user), db = Depends(get_db)):
#           return (
#               db.query(Query)
#                 .filter(Query.user_id == user.id)
#                 .order_by(Query.created_at.desc())
#                 .limit(50)
#                 .all()
#           )
