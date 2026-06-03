"""Embeddings via Voyage AI (hosted).

Replaces project 1's local sentence-transformers/bge model. Why hosted:
  * No torch in the image — build is far smaller/faster and the service
    runs comfortably in ~512 MB instead of needing 1 GB+ for CPU torch.
  * Higher retrieval quality from a frontier embedding model.

Trade-off vs local: every embed call is a network round-trip and costs
tokens (the voyage-4 family includes a generous monthly free tier). For a
multi-user web app that already calls a hosted LLM, that's the right call.

Voyage returns L2-normalized vectors, so cosine similarity in Qdrant
reduces to a dot product — consistent with the COSINE collection.

`input_type` is the Voyage equivalent of bge's query prefix: pass
"query" at retrieval time and "document" at ingestion time so the two
representations are aligned.
"""
import voyageai

from app.config import settings

# All voyage-4 models default to 1024 dims; we also pass output_dimension
# explicitly so the vector size is pinned regardless of model defaults —
# it MUST match the Qdrant collection's configured size.
EMBEDDING_DIM = 1024

# Voyage accepts up to 1,000 inputs per request; we batch smaller to stay
# well under the per-request token ceiling (chunks are ~500 tokens each).
_BATCH_SIZE = 128

_client: voyageai.Client | None = None


def _get_client() -> voyageai.Client:
    """Lazy singleton accessor for the Voyage client."""
    global _client
    if _client is None:
        if not settings.VOYAGE_API_KEY:
            raise RuntimeError(
                "VOYAGE_API_KEY is not set. Add it to the environment "
                "(.env locally, Render env var in production)."
            )
        _client = voyageai.Client(api_key=settings.VOYAGE_API_KEY)
    return _client


def embed_query(text: str) -> list[float]:
    """Embed a single query string (used at retrieval time)."""
    result = _get_client().embed(
        [text],
        model=settings.VOYAGE_MODEL,
        input_type="query",
        output_dimension=EMBEDDING_DIM,
    )
    return result.embeddings[0]


def embed_batch(
    texts: list[str],
    batch_size: int = _BATCH_SIZE,
    show_progress: bool = False,
) -> list[list[float]]:
    """Embed a batch of documents (used at ingestion time).

    `show_progress` is accepted for call-site compatibility with the old
    local embedder; Voyage has no progress bar, so it's a no-op.
    """
    if not texts:
        return []

    client = _get_client()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        result = client.embed(
            batch,
            model=settings.VOYAGE_MODEL,
            input_type="document",
            output_dimension=EMBEDDING_DIM,
        )
        vectors.extend(result.embeddings)
    return vectors
