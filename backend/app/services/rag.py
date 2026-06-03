"""RAG service layer — the clean public API the HTTP endpoints call.

Two functions, both taking `user_id` as their first argument:

    ingest_document(user_id, document_id, file_bytes, filename) -> dict
    query(user_id, question, top_k=5)                           -> dict

Design contract (why this layer exists at all):
  * **Pure RAG, no Postgres.** This module talks only to the vector
    store and the LLM. Writing the `documents` / `queries` rows and
    measuring `response_time_ms` is the endpoint's job (Tasks 4-5).
    Keeping persistence out makes the RAG core trivially unit-testable
    and lets the isolation guarantee be verified without a database.
  * **`user_id` is always a parameter, never derived here.** Callers
    pass `str(current_user.id)` straight from the JWT (see
    app/auth/deps.py). This module has no notion of "the current user",
    so there is no path by which a request could read another user's
    corpus — the only user_id it ever sees is the one handed in.
  * **`document_id` is supplied by the caller**, not minted here, so it
    matches the primary key of the `documents` row the endpoint created.
"""
from io import BytesIO

from pypdf import PdfReader

from app.rag import vectorstore
from app.rag.chunking import chunk_documents
from app.rag.embeddings import EMBEDDING_DIM, embed_batch
from app.rag.generate import generate_answer
from app.rag.retrieval import retrieve


def ingest_document(
    user_id: str,
    document_id: str,
    file_bytes: bytes,
    filename: str,
) -> dict:
    """Ingest one uploaded PDF into the per-user vector corpus.

    Pipeline: read PDF pages -> chunk -> embed -> upsert with
    (user_id, document_id) stamped on every point.

    Args:
        user_id: Owner of the document — taken from the JWT by the caller.
        document_id: PK of the `documents` row this PDF belongs to.
        file_bytes: Raw PDF bytes (e.g. from an UploadFile.read()).
        filename: Original filename, stored for citation display.

    Returns:
        {"chunk_count": int} — how many chunks were indexed. 0 means the
        PDF had no extractable text (e.g. a scanned image without OCR).
    """
    vectorstore.init_collection(EMBEDDING_DIM)

    pages = _load_pdf_pages(file_bytes, filename)
    chunks = chunk_documents(pages)
    if not chunks:
        return {"chunk_count": 0}

    embeddings = embed_batch([c["text"] for c in chunks], show_progress=False)
    vectorstore.upsert(
        chunks,
        embeddings,
        user_id=user_id,
        document_id=document_id,
    )
    return {"chunk_count": len(chunks)}


def query(user_id: str, question: str, top_k: int = 5) -> dict:
    """Answer `question` using only `user_id`'s indexed documents.

    Retrieval is filtered to the user at the vector-store layer, so the
    chunks that reach Claude — and therefore the answer and its cited
    sources — can only come from that user's own corpus.

    Returns:
        {"answer": str, "sources": list[dict]} where each source is
        {"text", "filename", "page", "chunk_index", "document_id", "score"}.
    """
    chunks = retrieve(question, user_id=user_id, top_k=top_k)
    return generate_answer(question, chunks)


def _load_pdf_pages(file_bytes: bytes, filename: str) -> list[dict]:
    """Read a PDF from raw bytes into per-page records.

    Each record is {"filename": str, "page": int, "text": str}. Pages
    with no extractable text are skipped — they would only produce
    useless embeddings. Pages are 1-indexed to match human citation.
    """
    reader = PdfReader(BytesIO(file_bytes))
    records: list[dict] = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        records.append({"filename": filename, "page": page_num, "text": text})
    return records
