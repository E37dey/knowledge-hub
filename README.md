# Knowledge Hub

> A multi-user RAG platform. Users register, upload their own
> engineering documents, and ask grounded questions against their
> personal corpus — with per-user data isolation enforced in both
> PostgreSQL and Qdrant.

## Screenshots

![Login](docs/01-login.png)
*Login — JWT-based auth, redirects to the protected dashboard on success.*

![Empty dashboard](docs/02-dashboard-empty.png)
*Empty dashboard — every user starts with a private (empty) corpus.*

![Documents indexed](docs/03-dashboard-uploaded.png)
*Documents page after upload — synchronous ingestion shows the status flipping from "processing" to "indexed" with the chunk count.*

![Cited answer](docs/04-ask-answer.png)
*Cited answer — inline citations on every claim, source cards with similarity scores, and the user's per-account query history on the right.*

![Isolation](docs/05-isolation-userB-empty.png)
*User-B logged in: zero documents, despite user-A having uploaded. Postgres rows are FK-filtered; Qdrant points are payload-filtered. Same physical stores, hard logical separation.*

---

Knowledge Hub is the full-stack evolution of
[engineering-rag](../engineering-rag): same retrieval core, now wrapped
in authentication, persistence, and multi-tenancy. React frontend,
FastAPI backend, JWT auth, Postgres for relational state (users,
documents, query history), Qdrant for vectors. Every operation —
listing documents, retrieving chunks, browsing query history — is
filtered by the JWT-derived user, in both stores.

Two principles carry over from project 1 and shape every choice here:

1. **Every factual claim is cited inline** — `[filename, p.PAGE]` — so
   the answer always traces to a source page in the user's own corpus.
2. **Questions outside the corpus are refused, not guessed** — the
   model emits a verbatim refusal phrase instead of inventing a fact
   from its training data.

The new principle introduced by project 2:

3. **No data ever crosses a user boundary.** Not in the Postgres rows,
   not in the Qdrant payload filter, not transiently in process memory.
   Tested end-to-end by `scripts/verify_isolation.py` — see below.

---

## Architecture

```
[React + Vite dev server, :5173]
        │  /api/* fetch  (Authorization: Bearer <JWT>)
        │
[Vite proxy strips /api]
        │
        ▼
[FastAPI backend, :8001]
   /auth/register, /auth/login        → JWT
   /me                                → user from JWT
   /documents/upload, GET, DELETE     → per-user CRUD
   /query, /query/history             → per-user RAG + history
        │
        ├──► [PostgreSQL :5432]   users, documents, queries
        │       Anchored on user_id (FK, ON DELETE CASCADE).
        │       Every endpoint filters on the JWT user before touching a row.
        │
        ├──► [Qdrant :6334]   collection: knowledge_hub_docs
        │       Every point payload carries user_id + document_id.
        │       search() applies a server-side Filter, so vectors from
        │       another user are never even candidates.
        │
        └──► [Anthropic Claude API]   Sonnet 4.6, temperature=0.0
                System prompt is sent with cache_control: ephemeral.
                Sees only the asking user's retrieved chunks.
```

Code follows the same split:
`app/auth/`, `app/documents/`, `app/query/` are HTTP routers;
`app/rag/` (chunking, embeddings, vectorstore, retrieval, prompts,
generate) is the retrieval core, ported from project 1;
`app/services/rag.py` is the thin layer that glues uploads to the
vector store and queries to Claude.

---

## Stack

| Component | Choice | Why |
|---|---|---|
| Language | Python 3.11+ on the backend, modern JS (ES modules) on the frontend | Type hints + Pydantic for the contract surface; no build pipeline complexity for the UI beyond Vite |
| Frontend | React 18 + React Router 6, bundled with Vite | Multi-route app with auth context and form state — beyond what vanilla DOM is comfortable with |
| Backend | FastAPI + Pydantic | Typed request/response, auto-generated OpenAPI docs at `/docs`, ergonomic Depends-based auth |
| Database | PostgreSQL 16 in Docker | Production-grade, relational, transactional DDL (the alembic migration runs as a single atomic transaction), JSONB for storing query sources |
| ORM | SQLAlchemy 2 + Alembic | Versioned schema; the migration history lives in `backend/alembic/versions/` |
| Auth | JWT (`python-jose`) + bcrypt | Stateless, scales horizontally, no server-side session store |
| Password hashing | `bcrypt` package directly | Passlib's abstraction was useful for legacy migrations between hash schemes; we have no such problem, and recent passlib crashes on bcrypt 5.x. See "Security decisions" below |
| Vector DB | Qdrant in Docker (host port 6334) | Production-grade vector store with a real dashboard at `:6334/dashboard`, payload filters that run server-side, and a stable Python client |
| Embeddings | `sentence-transformers` / `BAAI/bge-small-en-v1.5` | Local, 384-dim, no external API, zero per-query cost — important for confidential corpora |
| LLM | Anthropic Claude Sonnet 4.6 | Strong instruction-following for the citation + refusal rules; `temperature=0.0` for determinism |
| Orchestration | docker-compose | Brings Postgres and Qdrant up with persistent volumes — restarts don't lose your index |

---

## Running from scratch

### Prerequisites
- Docker + Docker Compose
- Python 3.11+
- Node 18+ (for the React frontend)
- An Anthropic API key

### 1. Start the data plane

```bash
docker compose up -d
docker compose ps                  # both postgres and qdrant should be "Up"
```

Health checks:
- Postgres: `docker exec knowledge-hub-postgres pg_isready -U knowledge_hub`
- Qdrant:   `curl http://localhost:6334/collections`

### 2. Backend

```bash
cd backend
python -m venv .venv               # optional but recommended
.venv/Scripts/activate             # Windows; source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env               # then fill in SECRET_KEY and ANTHROPIC_API_KEY
py -m alembic upgrade head         # creates users, documents, queries
py -m uvicorn app.main:app --port 8001 --reload
```

The API is now at <http://localhost:8001>; Swagger UI at
<http://localhost:8001/docs>.

> **Port note.** Port 8000 is occupied on the development machine by an
> unrelated service, so the backend runs on 8001 here. To switch, change
> the port in both the `uvicorn` command and `frontend/vite.config.js`.

### 3. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Register a user and you'll land on the
dashboard. The frontend's `/api/*` calls are proxied to the FastAPI
backend by Vite, so there is no CORS configuration to maintain.

### 4. Verify per-user isolation (optional but worth it)

```bash
py scripts/verify_isolation.py
```

This is the eval for project 2 — see "Verifying isolation" below.

---

## Environment variables

All read by `app/config.py` via `pydantic-settings`, from
`backend/.env`. The `.env.example` is the canonical list.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | — | SQLAlchemy URL, e.g. `postgresql://knowledge_hub:knowledge_hub_dev@localhost:5432/knowledge_hub`. Matches `docker-compose.yml`. |
| `QDRANT_HOST` | no | `localhost` | Qdrant host (the docker-compose service maps to `localhost`). |
| `QDRANT_PORT` | no | `6334` | Host port for Qdrant. Shifted from the default `6333` to avoid colliding with project 1's instance. |
| `SECRET_KEY` | yes | — | HS256 signing key for JWTs. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `JWT_ALGORITHM` | no | `HS256` | JWT signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `60` | Token lifetime. |
| `ANTHROPIC_API_KEY` | yes | — | Anthropic API key. Required at request time, not at import time, so the API still boots without it. |

---

## Security decisions

These are the decisions I'd defend in a technical interview, with the
reasoning behind each.

### 1. Per-user isolation in two stores

The isolation guarantee lives in both layers — defence in depth, not a
single switch.

- **Postgres.** Every `Document` and `Query` row carries `user_id` as
  a foreign key with `ON DELETE CASCADE`. Every endpoint filters on
  `user_id == current_user.id` before reading. The `user_id` always
  comes from the validated JWT — never from the request body.
- **Qdrant.** Every point's payload carries `user_id` and `document_id`.
  `search()` applies a server-side `Filter` on `user_id`, so vectors
  from another user are never candidates — not even transiently in
  process memory. Keyword payload indexes on `user_id` and
  `document_id` keep the filter fast as the shared collection grows.

End-to-end check: `scripts/verify_isolation.py`.

### 2. 404, not 403, on cross-user document access

`DELETE /documents/{id}` scopes its query by both `id` AND `user_id`.
A document owned by another user resolves to "not found" — the same
response as a truly nonexistent id. This denies an attacker a probe to
enumerate which document ids exist in the system.

### 3. Generic 401 on login

"Invalid credentials." is returned for both unknown-email and
wrong-password failures. Distinguishing them would give an attacker a
user-enumeration oracle. Same principle applies to invalid JWTs (in
`get_current_user`) — every failure mode collapses to one 401 with the
RFC-prescribed `WWW-Authenticate: Bearer` header.

### 4. bcrypt directly, not through passlib

Mid-build, registration started returning 500. The traceback told the
story: passlib 1.7 reads `bcrypt.__about__.__version__` for version
detection, but `__about__` was removed in bcrypt 4.1; passlib's
exception handler then ran a bug-detection routine that built a long
test password, which bcrypt 5.0 rejected with a `ValueError` because
inputs >72 bytes are no longer accepted silently.

The fix wasn't to pin bcrypt down — it was to drop the abstraction
layer. The `bcrypt` package's API is two functions (`hashpw`,
`checkpw`) and hasn't changed in years; passlib was useful for legacy
systems migrating between hash schemes, which we have no need for.
`security.py` now uses bcrypt directly, with an explicit UTF-8 + 72-byte
truncation before hashing so a pathological password can't crash the
server.

### 5. JWT stateless with expiry

Tokens carry `sub` (the user UUID) and `exp` (default: 60 minutes). No
server-side session store; auth scales horizontally with the API. JWT
decode failures (missing, malformed, expired, forged signature, deleted
user) all surface as the same generic 401, so an attacker can't tell
which kind of failure they triggered.

### 6. `hashed_password` is never serialised

The Pydantic `UserPublic` response model has no `hashed_password`
field, and SQLAlchemy `User` rows pass through `from_attributes=True`
where only declared fields are exposed. The hash exists only in
Postgres and inside the bcrypt verify path. There is no route, on any
path, that emits it.

---

## Verifying isolation

`scripts/verify_isolation.py` is the eval for project 2. It hits the
running API and proves the isolation contract end-to-end:

```bash
py scripts/verify_isolation.py
```

Five checks:

1. Two users register and receive distinct JWTs.
2. Alice uploads a sample PDF; the row reports `status="indexed"`
   with a positive chunk count.
3. Alice's `/documents` returns exactly her one document.
4. Bob's `/documents` is empty — Postgres FK isolation.
5. Bob's `/query` returns zero sources and the verbatim refusal phrase —
   Qdrant payload isolation.

The script uses unique email addresses per run (`alice+<uuid>@...`) so
it is idempotent — re-running it doesn't require manual cleanup. By
default it deletes alice's uploaded document at the end; pass `--keep`
to leave it in place for inspection.

The default sample PDF is `engineering-rag/data/NE555.pdf` (the
project-1 corpus); pass `--pdf <path>` to point at any PDF on disk.

---

## Built with Claude Code

The full system was developed with Claude Code as an agentic partner.
The validation discipline from project 1 carried over: every claim of
"task complete" was treated as a hypothesis to confirm against the
underlying system, not the agent's narration. Two new lessons surfaced
specifically in this build.

**Compatibility hell in abstraction layers.** Most of the time, an
abstraction layer (`passlib` over `bcrypt`) is paying for itself. When
the layer crashes on the version of the underlying library you're
actually using, that's a signal to question whether you need the layer
at all. Section 4 of "Security decisions" above is the full story —
the actual takeaway is that the right fix is usually a layer removal,
not a version pin.

**Namespace package shadowing.** Early in task 1 the alembic CLI
appeared to be installed but `py -m alembic upgrade head` failed with
`No module named alembic.__main__`. The cause turned out to be that
the local `backend/alembic/` directory (our migrations folder) was
shadowing the unrelated `alembic` pip package — Python's import system
saw a directory named `alembic` in cwd, treated it as a namespace
package, and that hid the real package. The diagnostic signal:
`import alembic` works but `alembic.__file__ is None`. The fix was
trivial (`pip install alembic`); the lesson is that an opinionated
project layout can interact with the import system in ways no error
message will spell out for you.

Both fixes were ~10 lines of code. The cost was the time to recognise
what was actually happening, which is the part the agent couldn't do
on its own.

---

## Limitations and Future Work

**Known limitations**

- **Ingestion is synchronous.** `POST /documents/upload` blocks until
  chunking + embedding + Qdrant upsert finish. For a small datasheet
  this is ~5-15 seconds and acceptable; for a 200-page standard it
  would not be. In production this would be a background worker (RQ,
  Celery, or a lightweight asyncio task queue) writing the row as
  `processing` and flipping to `indexed` on completion. The schema
  already supports this — `Document.status` has the values.
- **No re-ranking.** Carries over from project 1 — a cross-encoder
  re-rank would filter out the occasional irrelevant chunk that
  slips into top-k on a borderline query.
- **No refresh tokens.** Access tokens expire after 60 minutes and the
  user has to log in again. A refresh-token endpoint is the natural
  next step; for a portfolio demo, single-token auth is enough to make
  the JWT + protected-route story legible.
- **No rate limiting.** A determined attacker could brute-force
  `/auth/login` against a known email. In production this would be a
  per-IP and per-email rate limit (e.g. `slowapi`, or a reverse-proxy
  rule).
- **Uploaded PDFs are not stored.** Only the extracted text → chunks →
  vectors land in Qdrant; the original bytes are discarded after
  ingestion. A re-ingest requires the user to re-upload. Adding S3 (or
  local disk in dev) for the original PDF is a small change but wasn't
  needed for the demo.
- **Minimal automated tests.** `scripts/verify_isolation.py` is the
  end-to-end check; per-unit pytest coverage is absent. The natural
  expansion is a `tests/` suite that uses `httpx.AsyncClient` against
  the live app with a Postgres test schema fixture.

**Planned upgrades**

- Background-job ingestion with status polling on the dashboard.
- Cross-encoder re-ranking (`bge-reranker-base`) before the answer
  prompt.
- Hybrid search (BM25 + dense) for queries dominated by exact terms
  like part numbers.
- Refresh tokens + rate limiting on `/auth/login`.
- A `tests/` suite with isolation, auth-edge-case, and prompt-snapshot
  coverage.
