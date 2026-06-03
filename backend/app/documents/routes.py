"""Document endpoints: upload, list, delete — all per-user.

Isolation contract:
  * Upload   -> Postgres row is tagged user_id; Qdrant payload too.
  * List     -> filtered by user_id.
  * Delete   -> verify document.user_id == current_user.id BEFORE
                touching anything. 404 if not found OR not owned —
                same response to avoid leaking row existence.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/documents", tags=["documents"])


# TODO: @router.post("/upload", response_model=DocumentPublic, status_code=201)
#       async def upload(
#           file: UploadFile = File(...),
#           user: User = Depends(get_current_user),
#           db: Session = Depends(get_db),
#       ):
#           - validate content_type == "application/pdf"
#           - persist Document row (status="processing")
#           - run ingestion: chunk -> embed -> upsert (with user_id payload)
#           - update Document (status="indexed", chunk_count=N)
#           - on exception: status="failed", re-raise as 500


# TODO: @router.get("/", response_model=list[DocumentPublic])
#       def list_my_docs(user = Depends(get_current_user), db = Depends(get_db)):
#           return db.query(Document).filter(Document.user_id == user.id).all()


# TODO: @router.delete("/{doc_id}", status_code=204)
#       def delete(doc_id: UUID, user = Depends(get_current_user), db = Depends(get_db)):
#           - fetch document; 404 if not found OR user_id != user.id
#           - vectorstore.delete_by_document_id(doc_id)
#           - db.delete + commit
