# Knowledge Hub

> Multi-user RAG platform. Users register, upload their own engineering
> documents, and ask grounded questions against their personal corpus —
> with per-user data isolation enforced in both PostgreSQL and Qdrant.

This is a full-stack evolution of [engineering-rag](../engineering-rag) —
same retrieval core, now wrapped in authentication, persistence, and
multi-tenancy.

## Status

**Scaffolding (Task 0).** Repository structure is in place; no
functionality wired up yet. See `PROJECT_2_SPEC.md` for the roadmap and
`CLAUDE.md` for working principles.

## Stack (planned)

- **Frontend:** React + Vite
- **Backend:** FastAPI
- **Database:** PostgreSQL 16 (Docker)
- **ORM:** SQLAlchemy + Alembic
- **Auth:** JWT (`python-jose`) + bcrypt (`passlib`)
- **Vector DB:** Qdrant (Docker, host port 6334)
- **LLM:** Anthropic Claude Sonnet 4.6
- **Embeddings:** `sentence-transformers` / `BAAI/bge-small-en-v1.5`

## Quick start (Task 0 verification only)

```bash
docker compose up -d
docker compose ps        # both postgres and qdrant should be "Up"
```

Health checks:
- Postgres: `docker exec knowledge-hub-postgres pg_isready -U knowledge_hub`
- Qdrant:   `curl http://localhost:6334/collections`

(Full run instructions land as features come online in later tasks.)
