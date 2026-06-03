"""All Qdrant interaction lives here.

Nothing else in the codebase should import `qdrant_client` directly — if
we ever swap the DB (Weaviate, pgvector, …) this is the one file to
rewrite.

Per-user isolation (the difference from project 1):
    * Every point's payload carries `user_id` and `document_id`.
    * `search()` ALWAYS filters on `user_id` server-side — we never
      fetch-then-filter in Python, which would open a race window where
      another user's vectors transit our process memory.
    * `user_id` and `document_id` get keyword payload indexes so the
      filter is both correct and fast.

Collection layout:
    name:     knowledge_hub_docs   (single shared collection)
    distance: cosine  (vectors are L2-normalized at embed time, so cosine
              is equivalent to a dot product and Qdrant can exploit that)
    payload:  user_id, document_id, filename, page, chunk_index, text

Point IDs are deterministic UUID5 hashes over (document_id, page,
chunk_index). Keying on `document_id` — a per-upload UUID — rather than
on `filename` (as project 1 did) is what prevents two users who upload
the same filename from overwriting each other's vectors. Re-ingesting
the *same* document overwrites its own points instead of duplicating
them, so the pipeline stays idempotent.

Connection target comes from `settings` (host port 6334 → container
6333 in docker-compose), never hardcoded.
"""
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.config import settings

COLLECTION_NAME = "knowledge_hub_docs"

# Bigger than this and the HTTP body for a single upsert request grows
# uncomfortably (~1.5 KB vector + ~2 KB text payload per point).
UPSERT_BATCH = 128

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    """Lazy singleton accessor for the Qdrant client."""
    global _client
    if _client is None:
        # check_compatibility=False silences a client/server version
        # warning that's noisy and not actionable in our setup.
        _client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            check_compatibility=False,
        )
    return _client


def init_collection(vector_size: int) -> None:
    """Create the shared collection + payload indexes if absent (idempotent).

    We deliberately do NOT recreate on re-run — the UUID5 point IDs make
    upsert overwrite-safe, so dropping the collection would only throw
    away the work done so far.
    """
    client = _get_client()
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
    # Keyword indexes on the isolation fields. Filtering works without an
    # index, but an explicit keyword index keeps user-scoped search fast
    # as the shared collection grows across many users.
    _ensure_payload_index("user_id")
    _ensure_payload_index("document_id")


def _ensure_payload_index(field_name: str) -> None:
    """Create a keyword payload index, tolerating "already exists"."""
    client = _get_client()
    try:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field_name,
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except Exception:
        # Index already present from a previous run — Qdrant treats a
        # redundant create as an error; for us it's a no-op.
        pass


def upsert(
    chunks: list[dict],
    embeddings: list[list[float]],
    user_id: str,
    document_id: str,
) -> None:
    """Store chunks + embeddings + isolation metadata. Lengths must match.

    Every point's payload carries `user_id` (the isolation key that
    `search` filters on) and `document_id` (so a deleted document can be
    purged precisely, and so each retrieved source can be attributed).
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"chunks/embeddings length mismatch: {len(chunks)} vs {len(embeddings)}"
        )
    if not chunks:
        return

    client = _get_client()
    points = [
        PointStruct(
            id=_chunk_id(document_id, chunk),
            vector=vector,
            payload={
                "user_id": user_id,
                "document_id": document_id,
                "filename": chunk["filename"],
                "page": chunk["page"],
                "chunk_index": chunk["chunk_index"],
                "text": chunk["text"],
            },
        )
        for chunk, vector in zip(chunks, embeddings)
    ]

    for start in range(0, len(points), UPSERT_BATCH):
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points[start : start + UPSERT_BATCH],
        )


def search(
    query_embedding: list[float],
    user_id: str,
    top_k: int = 5,
) -> list[dict]:
    """Return the top_k most similar chunks **owned by `user_id`**.

    The `query_filter` is applied by Qdrant before scoring, so vectors
    belonging to other users are never even candidates — isolation is
    enforced in the database, not in this process.
    """
    client = _get_client()
    user_filter = Filter(
        must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
    )
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        query_filter=user_filter,
        limit=top_k,
    )
    return [
        {
            "text": hit.payload["text"],
            "filename": hit.payload["filename"],
            "page": hit.payload["page"],
            "chunk_index": hit.payload["chunk_index"],
            "document_id": hit.payload["document_id"],
            "score": hit.score,
        }
        for hit in response.points
    ]


def delete_by_document_id(document_id: str) -> None:
    """Remove every point belonging to a deleted document.

    Used by the documents endpoint in Task 4. Keyed on document_id so a
    single delete is precise even within one user's corpus.
    """
    client = _get_client()
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="document_id", match=MatchValue(value=document_id)
                )
            ]
        ),
    )


def count(user_id: str | None = None) -> int:
    """Count points in the collection, optionally scoped to one user.

    Used by the isolation verification script and handy for debugging.
    """
    client = _get_client()
    count_filter = None
    if user_id is not None:
        count_filter = Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        )
    return client.count(
        collection_name=COLLECTION_NAME,
        count_filter=count_filter,
        exact=True,
    ).count


def _chunk_id(document_id: str, chunk: dict) -> str:
    """Deterministic UUID5 ID for a chunk — stable across re-runs.

    Keyed on document_id (not filename) so distinct uploads — even of
    the same filename by different users — never collide.
    """
    key = f"{document_id}::{chunk['page']}::{chunk['chunk_index']}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))
