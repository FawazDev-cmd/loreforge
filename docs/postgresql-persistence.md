# PostgreSQL Persistence Foundation

Day 34 adds LoreForge's first durable relational metadata layer. It is intentionally narrow: PostgreSQL stores document catalog entries and indexing-attempt state, while semantic vector search and BM25 lexical search remain in memory until Day 35.

## Architecture Boundary

Dependency direction stays clean:

```text
FastAPI routes
  -> application services
  -> LoreForge repository protocols
  -> SQLAlchemy repository adapters
  -> PostgreSQL
```

The domain-facing contracts remain framework independent:

- `CatalogRepository` in `loreforge.catalog.repository`
- `IndexingStateRepository` in `loreforge.indexing.state`

The SQLAlchemy adapters live in `loreforge.database` and are selected only by the application composition root when `LOREFORGE_DATABASE_URL` is configured.

## Stored Metadata

The initial migration creates:

- `documents`: catalog metadata, lifecycle status, page count, and chunk count.
- `indexing_states`: one row per indexing attempt with STARTED, SUCCEEDED, or FAILED state plus safe counts and timestamps.

The database does not store original PDF bytes, parsed pages, chunks, embeddings, vector index data, BM25 statistics, query observations, or evaluation records in Day 34.

## Runtime Selection

Leave `LOREFORGE_DATABASE_URL` empty for the default local runtime. In that mode, the catalog and indexing-state repositories are in memory and zero-cost.

Set `LOREFORGE_DATABASE_URL` to a PostgreSQL connection string to use durable metadata repositories. `postgres://` and `postgresql://` URLs are normalized to SQLAlchemy's `postgresql+psycopg://` driver form internally.

Supabase is treated only as a PostgreSQL host. No Supabase-specific database API is used.

## Migrations

Apply migrations before using a fresh configured database:

```bash
uv run --locked alembic -c alembic.ini upgrade head
```

The Alembic environment loads `LOREFORGE_DATABASE_URL` through LoreForge's typed settings. Application startup can also run migrations when `LOREFORGE_DATABASE_MIGRATIONS_ENABLED=true`, but this is disabled by default to keep local startup predictable.

## Health Check

`DatabaseRuntime.check_health()` performs a simple `SELECT 1` through the configured session factory. The public `/health` endpoint remains an application liveness check and does not expose database status.

## Tests

Default tests are offline and deterministic. SQLAlchemy repository tests use an isolated in-memory SQLite engine to verify repository behavior without requiring PostgreSQL.

A live PostgreSQL/Supabase smoke test is available but skipped unless explicitly enabled:

```bash
LOREFORGE_RUN_LIVE_DATABASE_SMOKE=true uv run --locked pytest tests/integration/test_database_live_smoke.py
```

Use the live smoke test only with a local ignored `.env` that contains a non-committed `LOREFORGE_DATABASE_URL`.

## Current Limitations

- Semantic vector retrieval remains backed by `InMemoryVectorIndex`.
- BM25 lexical retrieval remains backed by `InMemoryBM25Index`.
- Stored metadata can survive restart, but indexed retrieval evidence is rebuilt only while the process is alive.
- Original document storage is still a future milestone.
- Authentication and ownership are still future milestones.
