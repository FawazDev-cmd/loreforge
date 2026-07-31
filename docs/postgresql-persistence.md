# PostgreSQL Persistence Foundation

LoreForge uses PostgreSQL through SQLAlchemy and Alembic for durable relational state while keeping domain and application services behind LoreForge-owned repository protocols.

## Architecture Boundary

Dependency direction stays clean:

```text
FastAPI routes
  -> application services
  -> LoreForge repository protocols
  -> SQLAlchemy repository adapters
  -> PostgreSQL
```

The SQLAlchemy adapters live in `loreforge.database` and are selected only by the application composition root when `LOREFORGE_DATABASE_URL` is configured. With no database URL, LoreForge keeps the default zero-cost in-memory runtime.

## Stored State

Current migrations cover:

- document catalog metadata, lifecycle status, ownership, page count, and chunk count
- indexing-state attempts and safe lifecycle metadata
- user records used by API-key authentication
- persisted document chunks
- persisted embedding vectors and embedding metadata
- retrieval metadata needed by the repository-backed retrieval path

The database does not store original uploaded PDF bytes, prompt text, generated answers, provider payloads, raw observability traces, or evaluation reports.

## Runtime Selection

Leave `LOREFORGE_DATABASE_URL` empty for default local startup. Set it to a PostgreSQL connection string to use durable repositories. `postgres://` and `postgresql://` URLs are normalized to SQLAlchemy's `postgresql+psycopg://` driver form internally.

Supabase is treated only as a PostgreSQL host. No Supabase-specific database API is used.

## Migrations

Apply migrations before using a fresh configured database:

```bash
uv run --locked alembic -c alembic.ini upgrade head
```

Application startup can also run migrations when `LOREFORGE_DATABASE_MIGRATIONS_ENABLED=true`, but this is disabled by default to keep local startup predictable.

## Health Check

`DatabaseRuntime.check_health()` performs a simple `SELECT 1` through the configured session factory for diagnostics and tests. Public `/health` remains process liveness, and `/ready` reports only in-process lifecycle readiness.

## Tests

Default tests are offline and deterministic. SQLAlchemy repository tests use isolated in-memory SQLite where practical to verify repository behavior without requiring PostgreSQL.

A live PostgreSQL/Supabase smoke test is available but skipped unless explicitly enabled:

```bash
LOREFORGE_RUN_LIVE_DATABASE_SMOKE=true uv run --locked pytest tests/integration/test_database_live_smoke.py
```

Use the live smoke test only with a local ignored `.env` that contains a non-committed `LOREFORGE_DATABASE_URL`.

## Current Limitations

- Original uploaded PDF bytes are not durably stored.
- Runtime vector and BM25 structures still need an explicit rebuild/runbook after restart or redeploy.
- Rebuilds currently depend on persisted metadata, chunks, and embeddings rather than replaying original source files.
- A full production rebuild strategy should add durable file/object storage, content-addressed blobs, backup/restore procedures, and a rebuild worker or operational runbook.