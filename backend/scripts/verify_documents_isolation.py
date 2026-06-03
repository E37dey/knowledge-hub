"""End-to-end verification that documents are isolated between users.

This is the Task-4 checkpoint artifact. It drives the REAL FastAPI app
through an in-process HTTP client (no running uvicorn needed) and asserts
the full isolation contract for the documents endpoints:

  1. A user lists only their OWN documents.
  2. User B never sees user A's documents.
  3. User B cannot delete user A's document (404, not 403 — we don't even
     admit the row exists).
  4. Deleting a document purges its vectors from Qdrant too, scoped to
     the owner — the other user's vectors are untouched.

It exercises the whole stack: Postgres (rows), the RAG service (chunk +
embed + upsert), and Qdrant (filtered vectors). Small PDFs are generated
on the fly with reportlab, so the test is self-contained and fast.

Prerequisites: Postgres + Qdrant running (docker compose up -d) with
migrations applied (py -m alembic upgrade head). First run downloads the
bge embedding model.

Run from backend/:
    py -m scripts.verify_documents_isolation
"""
import sys
import uuid
from io import BytesIO

# Windows consoles default to cp1252 and crash on non-ASCII output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.database import SessionLocal
from app.main import app
from app.models import User
from app.rag import vectorstore

client = TestClient(app)

# Unique per run so re-runs don't collide on the unique email constraint.
_RUN = uuid.uuid4().hex[:8]
A_EMAIL = f"alice_{_RUN}@example.com"
B_EMAIL = f"bob_{_RUN}@example.com"
PASSWORD = "correct horse battery staple"


def _make_pdf(text: str) -> bytes:
    """Generate a one-page PDF containing `text`."""
    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def _register_and_login(email: str) -> tuple[str, str]:
    """Register a user and return (user_id, bearer_token)."""
    reg = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert reg.status_code == 201, f"register failed: {reg.status_code} {reg.text}"
    user_id = reg.json()["id"]

    login = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, f"login failed: {login.status_code} {login.text}"
    return user_id, login.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _upload(token: str, filename: str, text: str):
    return client.post(
        "/documents/upload",
        files={"file": (filename, _make_pdf(text), "application/pdf")},
        headers=_auth(token),
    )


def main() -> int:
    failures: list[str] = []
    a_user_id = b_user_id = None
    doc_a_id = doc_b_id = None

    print("=" * 70)
    print("PER-USER DOCUMENT ISOLATION VERIFICATION (end-to-end)")
    print("=" * 70)

    try:
        # --- Setup: two users -------------------------------------------
        print("\n[1] Registering + logging in two users...")
        a_user_id, token_a = _register_and_login(A_EMAIL)
        b_user_id, token_b = _register_and_login(B_EMAIL)
        print(f"    user A = {a_user_id}")
        print(f"    user B = {b_user_id}")

        # --- A uploads a document ---------------------------------------
        print("\n[2] User A uploads a PDF...")
        res = _upload(token_a, "alice_lm358.pdf",
                      "The LM358 is a dual operational amplifier operating from 3V to 32V.")
        if res.status_code != 201:
            failures.append(f"A upload failed: {res.status_code} {res.text}")
        else:
            body = res.json()
            doc_a_id = body["id"]
            print(f"    -> id={doc_a_id} status={body['status']} chunks={body['chunk_count']}")
            if body["status"] != "indexed" or body["chunk_count"] < 1:
                failures.append(f"A's document not indexed properly: {body}")

        # --- A sees it; B does NOT --------------------------------------
        print("\n[3] Listing documents for each user...")
        a_list = client.get("/documents", headers=_auth(token_a)).json()
        b_list = client.get("/documents", headers=_auth(token_b)).json()
        print(f"    user A sees {len(a_list)} doc(s); user B sees {len(b_list)} doc(s)")
        if len(a_list) != 1 or a_list[0]["id"] != doc_a_id:
            failures.append("user A does not see exactly their own document")
        if len(b_list) != 0:
            failures.append("ISOLATION BREACH: user B can see user A's documents")
        else:
            print("    -> user B cannot see user A's document. [OK]")

        # --- B uploads its own; lists stay separate ---------------------
        print("\n[4] User B uploads its own PDF; lists must stay separate...")
        res_b = _upload(token_b, "bob_ne555.pdf",
                        "The NE555 timer in astable mode generates a square-wave oscillator.")
        if res_b.status_code != 201:
            failures.append(f"B upload failed: {res_b.status_code} {res_b.text}")
        else:
            doc_b_id = res_b.json()["id"]
        a_list = client.get("/documents", headers=_auth(token_a)).json()
        b_list = client.get("/documents", headers=_auth(token_b)).json()
        print(f"    user A sees {len(a_list)} doc(s); user B sees {len(b_list)} doc(s)")
        if [d["id"] for d in a_list] != [doc_a_id]:
            failures.append("user A's list changed after user B uploaded")
        if [d["id"] for d in b_list] != [doc_b_id]:
            failures.append("user B sees something other than exactly its own doc")

        # --- B cannot delete A's document -------------------------------
        print("\n[5] ATTACK: user B tries to DELETE user A's document...")
        attack = client.delete(f"/documents/{doc_a_id}", headers=_auth(token_b))
        print(f"    -> HTTP {attack.status_code} (expected 404)")
        if attack.status_code != 404:
            failures.append(f"ISOLATION BREACH: B's delete of A's doc returned {attack.status_code}")
        else:
            print("    -> user B cannot delete user A's document. [OK]")
        still_there = client.get("/documents", headers=_auth(token_a)).json()
        if [d["id"] for d in still_there] != [doc_a_id]:
            failures.append("user A's document disappeared after B's delete attempt")

        # --- Vector layer is partitioned --------------------------------
        print("\n[6] Vector counts per user (Qdrant)...")
        a_vec = vectorstore.count(user_id=a_user_id)
        b_vec = vectorstore.count(user_id=b_user_id)
        print(f"    user A vectors={a_vec}, user B vectors={b_vec}")
        if a_vec < 1 or b_vec < 1:
            failures.append("expected each user to own at least one vector")

        # --- Delete cascades to vectors, scoped to owner ----------------
        print("\n[7] User A deletes its document; vectors must be purged (A only)...")
        d = client.delete(f"/documents/{doc_a_id}", headers=_auth(token_a))
        print(f"    -> HTTP {d.status_code} (expected 204)")
        if d.status_code != 204:
            failures.append(f"A's delete of its own doc returned {d.status_code}")
        a_after = client.get("/documents", headers=_auth(token_a)).json()
        a_vec_after = vectorstore.count(user_id=a_user_id)
        b_vec_after = vectorstore.count(user_id=b_user_id)
        print(f"    after delete: A docs={len(a_after)}, A vectors={a_vec_after}, B vectors={b_vec_after}")
        if len(a_after) != 0:
            failures.append("user A still has documents after deleting its only one")
        if a_vec_after != 0:
            failures.append("user A's vectors were not purged on delete")
        if b_vec_after < 1:
            failures.append("deleting user A's document also removed user B's vectors")
        else:
            print("    -> user A purged, user B untouched. [OK]")

    finally:
        # --- Cleanup: vectors + users (cascades to their rows) ----------
        print("\n[*] Cleaning up test users and vectors...")
        for did in (doc_a_id, doc_b_id):
            if did:
                vectorstore.delete_by_document_id(did)
        db = SessionLocal()
        try:
            for uid in (a_user_id, b_user_id):
                if uid:
                    u = db.query(User).filter(User.id == uuid.UUID(uid)).first()
                    if u:
                        db.delete(u)
            db.commit()
        finally:
            db.close()

    print("\n" + "=" * 70)
    if failures:
        print("RESULT: FAIL")
        for f in failures:
            print(f"  - {f}")
        print("=" * 70)
        return 1
    print("RESULT: PASS - documents are isolated per user across Postgres + Qdrant.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
