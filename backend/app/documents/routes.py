"""Document endpoints: upload, list, delete — all per-user.

Isolation contract:
  * Upload  -> the Postgres row is tagged with user_id, and every Qdrant
               chunk gets the same user_id in its payload (via the RAG
               service). user_id always comes from the JWT, never the body.
  * List    -> filtered by user_id; a user sees only their own documents.
  * Delete  -> verify document.user_id == current_user.id BEFORE touching
               anything. 404 if not found OR not owned — the SAME response
               either way, so the endpoint never leaks whether a given
               document id exists under another account.

Ingestion is synchronous (a known limitation noted in CLAUDE.md): the
request blocks until chunking + embedding + upsert finish. In production
this would be a background job with the row sitting in "processing" until
a worker flips it to "indexed".
"""
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Document, User
from app.rag import vectorstore
from app.schemas import DocumentPublic
from app.services import rag as rag_service

router = APIRouter(prefix="/documents", tags=["documents"])

# Guard against pathological uploads. The datasheets this is built for
# are a few MB; 20 MB is generous headroom without inviting abuse.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.post(
    "/upload",
    response_model=DocumentPublic,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    """Upload a PDF, ingest it into the user's private corpus, return the row.

    Flow: validate -> create the `documents` row (so we have a stable
    document_id to stamp on every chunk) -> ingest -> flip status to
    "indexed". Any ingestion failure marks the row "failed" so the user
    can see the attempt rather than having it vanish.
    """
    filename = file.filename or "upload.pdf"
    if file.content_type != "application/pdf" and not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 20 MB upload limit.",
        )

    # Create the row first: its primary key becomes the document_id that
    # tags every chunk in Qdrant, so ownership is consistent across both
    # stores even if ingestion later fails.
    document = Document(user_id=user.id, filename=filename, status="processing")
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        result = rag_service.ingest_document(
            user_id=str(user.id),
            document_id=str(document.id),
            file_bytes=file_bytes,
            filename=filename,
        )
    except Exception:
        document.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process the document.",
        )

    chunk_count = result["chunk_count"]
    if chunk_count == 0:
        # A readable PDF that yielded no text (e.g. scanned images) — keep
        # the row as a "failed" record and tell the user why.
        document.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No extractable text found in the PDF.",
        )

    document.status = "indexed"
    document.chunk_count = chunk_count
    db.commit()
    db.refresh(document)
    return document


@router.get("", response_model=list[DocumentPublic])
def list_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Document]:
    """List the current user's documents, newest first."""
    return (
        db.query(Document)
        .filter(Document.user_id == user.id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete one of the current user's documents, vectors included.

    The query is scoped by BOTH id and user_id, so another user's
    document id resolves to "not found" rather than being deletable.
    Vectors are purged from Qdrant before the row is removed: if the
    vector delete fails the row survives and the operation can be retried,
    avoiding an orphaned set of chunks with no owning row.
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user.id)
        .first()
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    vectorstore.delete_by_document_id(str(document.id))
    db.delete(document)
    db.commit()
