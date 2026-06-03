"""Semantic search over the indexed corpus — now per-user.

Thin orchestration layer: embed the query, hit the vector store with the
caller's `user_id`, return chunks. Kept separate so higher layers (the
service in app/services/rag.py) depend on `retrieve`, not on embeddings
or Qdrant directly.

Difference from project 1: `user_id` is a required argument and is
threaded straight into the vector-store filter. There is no code path
that retrieves without it.
"""
from app.rag.embeddings import embed_query
from app.rag.vectorstore import search


def retrieve(query: str, user_id: str, top_k: int = 5) -> list[dict]:
    """Embed `query` and return top_k chunks belonging to `user_id`.

    Each result is shaped as
    {"text", "filename", "page", "chunk_index", "document_id", "score"}.
    """
    vector = embed_query(query)
    return search(vector, user_id=user_id, top_k=top_k)
