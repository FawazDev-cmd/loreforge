# Dependency Audit

LoreForge keeps runtime and development dependencies separate in `pyproject.toml`.
No dependency was removed for Day 40 because each current dependency supports an
implemented capability or verification workflow.

## Runtime Dependencies

`fastapi`

- Purpose: HTTP API presentation layer.
- Why required: health, readiness, admin, document, AskMe, and metrics routes.
- Future replacement: another ASGI framework, if presentation needs change.

`uvicorn`

- Purpose: ASGI server for local and container runtime.
- Why required: run the FastAPI application.
- Future replacement: Gunicorn/Uvicorn workers or another ASGI process manager.

`python-multipart`

- Purpose: multipart PDF upload parsing.
- Why required: document upload and indexing endpoints accept uploaded PDFs.
- Future replacement: direct object-storage ingestion.

`pypdf`

- Purpose: page-aware PDF parsing.
- Why required: deterministic PDF ingestion pipeline.
- Future replacement: a richer parser if layout or OCR requirements grow.

`sentence-transformers`

- Purpose: optional local embedding and reranking providers.
- Why required: zero-cost/local provider path.
- Future replacement: hosted embedding/reranker providers behind existing
  provider contracts.

`google-genai`

- Purpose: Gemini embedding and generation adapters.
- Why required: first real production provider integration.
- Future replacement: another provider adapter behind LoreForge-owned protocols.

`sqlalchemy`

- Purpose: relational persistence models and repository adapters.
- Why required: durable catalog, indexing state, chunks, embeddings, users, and
  ownership metadata.
- Future replacement: another persistence adapter behind repository protocols.

`psycopg[binary]`

- Purpose: PostgreSQL driver.
- Why required: SQLAlchemy PostgreSQL runtime.
- Future replacement: managed driver packaging or a different DB adapter.

`alembic`

- Purpose: schema migrations.
- Why required: versioned PostgreSQL schema changes.
- Future replacement: another migration tool, if the persistence strategy changes.

## Development Dependencies

`pytest`

- Purpose: deterministic unit, service, API, integration, and regression tests.

`httpx`

- Purpose: FastAPI/Starlette test client support.

`ruff`

- Purpose: linting and formatting.

`mypy`

- Purpose: static type checking over `src`.

## Audit Notes

- Live provider tests are opt-in and skipped by default.
- No dashboard, tracing vendor, vector database, Redis, frontend framework, or
  Kubernetes dependency is present.
- Model-heavy dependencies load lazily through explicit provider construction,
  not default import/startup.
