"""End-to-end verification of the /query endpoints — isolation + history.

This is the Task-5 checkpoint artifact. It drives the real FastAPI app
through an in-process client and proves:

  PHASE 1 — isolation + persistence (no API cost):
    The answer generator is replaced with a spy that records exactly
    which chunks it was handed. User A asks a question aimed at user B's
    topic; we assert that ONLY user A's chunks ever reach the generator
    or appear in the response/persisted sources — even though B's chunks
    are the better semantic match. Then we check /query/history is
    per-user: A never sees B's questions and vice versa.

    Why patch the LLM here: isolation is enforced at retrieval, BELOW
    generation. Spying on the generator's input is the most direct way
    to prove no foreign chunk crosses the boundary — and it costs nothing.

  PHASE 2 — real grounded answer (only if ANTHROPIC_API_KEY is set):
    The real generator is restored and user A asks about its OWN corpus,
    so you can see a genuine Claude answer with citations.

Prerequisites: Postgres + Qdrant running, migrations applied. First run
downloads the bge embedding model.

Run from backend/:
    py -m scripts.verify_query_isolation
"""
import sys
import uuid
from io import BytesIO

# Windows consoles default to cp1252 and crash on non-ASCII output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

import app.services.rag as rag_service_mod
from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import User
from app.rag import vectorstore

client = TestClient(app)

_RUN = uuid.uuid4().hex[:8]
A_EMAIL = f"alice_{_RUN}@example.com"
B_EMAIL = f"bob_{_RUN}@example.com"
PASSWORD = "correct horse battery staple"

# The chunks the (spied) generator was last handed — the exact context
# that would have been sent to Claude.
_captured: dict = {}


def _make_pdf(text: str) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def _register_and_login(email: str) -> tuple[str, str]:
    reg = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert reg.status_code == 201, f"register failed: {reg.status_code} {reg.text}"
    login = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, f"login failed: {login.status_code} {login.text}"
    return reg.json()["id"], login.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _upload(token: str, filename: str, text: str) -> str:
    res = client.post(
        "/documents/upload",
        files={"file": (filename, _make_pdf(text), "application/pdf")},
        headers=_auth(token),
    )
    assert res.status_code == 201, f"upload failed: {res.status_code} {res.text}"
    return res.json()["id"]


def _spy_generate(question: str, chunks: list[dict]) -> dict:
    """Stand-in for Claude: records the context, returns a deterministic stub."""
    _captured["chunks"] = chunks
    files = sorted({c["filename"] for c in chunks})
    label = ", ".join(files) if files else "no sources"
    return {"answer": f"[STUB answer grounded in: {label}]", "sources": chunks}


def main() -> int:
    failures: list[str] = []
    a_user_id = b_user_id = None
    doc_a_id = doc_b_id = None
    original_generate = rag_service_mod.generate_answer

    print("=" * 70)
    print("PER-USER QUERY ISOLATION + HISTORY VERIFICATION (end-to-end)")
    print("=" * 70)

    try:
        # --- Setup -------------------------------------------------------
        print("\n[1] Two users, each uploads one document on a different topic...")
        a_user_id, token_a = _register_and_login(A_EMAIL)
        b_user_id, token_b = _register_and_login(B_EMAIL)
        doc_a_id = _upload(token_a, "alice_lm358.pdf",
                           "The LM358 is a dual operational amplifier operating from 3V to 32V.")
        doc_b_id = _upload(token_b, "bob_ne555.pdf",
                           "The NE555 timer in astable mode generates a square-wave oscillator.")
        print(f"    A doc={doc_a_id}")
        print(f"    B doc={doc_b_id}")

        # === PHASE 1: isolation with a spied generator ===================
        rag_service_mod.generate_answer = _spy_generate

        print("\n[2] ATTACK: user A asks a question aimed at user B's topic (555 timer).")
        print("    Expectation: only user A's chunks reach the generator / response.")
        res = client.post(
            "/query",
            json={"question": "555 timer astable oscillator frequency capacitor", "top_k": 5},
            headers=_auth(token_a),
        )
        if res.status_code != 200:
            failures.append(f"A /query failed: {res.status_code} {res.text}")
        else:
            body = res.json()
            resp_sources = body["sources"]
            cap_sources = _captured.get("chunks", [])
            print(f"    answer: {body['answer']}")
            print(f"    response sources: {[s['filename'] for s in resp_sources]}")
            print(f"    response_time_ms: {body['response_time_ms']}")

            # Nothing from B may appear, in the response OR in what the
            # generator actually received.
            resp_leak = [s for s in resp_sources if s["document_id"] == doc_b_id]
            cap_leak = [c for c in cap_sources if c["document_id"] == doc_b_id]
            if resp_leak or cap_leak:
                failures.append(
                    f"ISOLATION BREACH: B's chunks reached A "
                    f"(response={len(resp_leak)}, generator={len(cap_leak)})"
                )
            elif not resp_sources:
                failures.append("A got zero sources — expected its own chunk(s)")
            else:
                print("    -> No user B chunks reached user A. [OK]")

        # --- History is per-user ----------------------------------------
        print("\n[3] Query history must be per-user...")
        a_hist = client.get("/query/history", headers=_auth(token_a)).json()
        b_hist = client.get("/query/history", headers=_auth(token_b)).json()
        print(f"    user A history={len(a_hist)}; user B history={len(b_hist)}")
        if len(a_hist) != 1:
            failures.append(f"user A history expected 1 item, got {len(a_hist)}")
        else:
            item = a_hist[0]
            if not isinstance(item["response_time_ms"], int) or not item["sources"]:
                failures.append("persisted query missing latency or sources")
        if len(b_hist) != 0:
            failures.append("ISOLATION BREACH: user B's history shows user A's query")
        else:
            print("    -> user B's history does not contain user A's query. [OK]")

        # B asks its own question; histories stay separate.
        client.post(
            "/query",
            json={"question": "What does the NE555 do in astable mode?", "top_k": 5},
            headers=_auth(token_b),
        )
        a_hist = client.get("/query/history", headers=_auth(token_a)).json()
        b_hist = client.get("/query/history", headers=_auth(token_b)).json()
        a_questions = {h["question"] for h in a_hist}
        if any("NE555" in q for q in a_questions):
            failures.append("ISOLATION BREACH: user B's question leaked into user A's history")
        if len(b_hist) != 1:
            failures.append(f"user B history expected 1 item, got {len(b_hist)}")

        # === PHASE 2: a real Claude answer over A's own corpus ===========
        rag_service_mod.generate_answer = original_generate
        print("\n[4] REAL Claude call: user A asks about its OWN document...")
        if not settings.ANTHROPIC_API_KEY:
            print("    (skipped — ANTHROPIC_API_KEY not set)")
        else:
            real = client.post(
                "/query",
                json={"question": "What is the supply voltage range of the LM358?", "top_k": 5},
                headers=_auth(token_a),
            )
            if real.status_code != 200:
                failures.append(f"real /query failed: {real.status_code} {real.text}")
            else:
                rb = real.json()
                print(f"    Q: What is the supply voltage range of the LM358?")
                print(f"    A: {rb['answer']}")
                print(f"    sources: {[(s['filename'], 'p.%d' % s['page']) for s in rb['sources']]}")
                print(f"    response_time_ms: {rb['response_time_ms']}")
                if not rb["answer"].strip():
                    failures.append("real query returned an empty answer")
                if any(s["document_id"] == doc_b_id for s in rb["sources"]):
                    failures.append("ISOLATION BREACH: real answer cited user B's document")

    finally:
        rag_service_mod.generate_answer = original_generate
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
    print("RESULT: PASS - queries + history are isolated per user.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
