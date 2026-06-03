"""All Qdrant interaction lives here.

Key difference from project 1: every point's payload carries
`user_id` and `document_id`, and `search()` always filters on
`user_id`. This is the vector-layer half of the per-user isolation
guarantee.

To be implemented in Task 3 (initial port) and Task 4 (delete-by-doc).
"""

COLLECTION_NAME = "knowledge_hub_docs"


def init_collection(vector_size: int) -> None:
    """Create the shared collection if it doesn't exist (idempotent)."""
    # TODO: as in project 1 — single collection, COSINE distance
    raise NotImplementedError


def upsert(
    chunks: list[dict],
    embeddings: list[list[float]],
    user_id: str,
    document_id: str,
) -> None:
    """Store chunks with isolation-critical metadata.

    Each point's payload MUST include user_id and document_id so that
    retrieval can filter and document deletion can target precisely.
    """
    # TODO: payload = {**chunk_fields, "user_id": user_id, "document_id": document_id}
    raise NotImplementedError


def search(
    query_embedding: list[float],
    user_id: str,
    top_k: int = 5,
) -> list[dict]:
    """Return top_k chunks owned by `user_id`.

    Filtering happens server-side via Qdrant's Filter — we never
    fetch then filter in Python, which would race-window leak data.
    """
    # TODO: Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])
    raise NotImplementedError


def delete_by_document_id(document_id: str) -> None:
    """Remove every point belonging to a deleted document."""
    # TODO: client.delete with Filter on document_id
    raise NotImplementedError
