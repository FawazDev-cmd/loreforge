# Developer Onboarding

This guide is for a new engineer taking over LoreForge from a fresh clone.

## Clone

```powershell
git clone <repository-url>
cd loreforge
```

Do not commit `.env`, provider keys, database URLs, local reports, model caches,
or private documents.

## Install

LoreForge uses Python 3.13, `uv`, Node.js, and npm.

Backend:

```powershell
uv sync --all-groups
```

Frontend:

```powershell
cd frontend
npm install
```

## Configure

Copy the environment template only when you need local overrides:

```powershell
Copy-Item .env.example .env
```

The default runtime is intentionally zero-cost:

- providers disabled
- auth disabled
- PostgreSQL disabled
- in-memory catalog/index runtime
- no live provider calls

Enable only what you need for the current task.

## Migrate

When `LOREFORGE_DATABASE_URL` is set for PostgreSQL:

```powershell
uv run --locked alembic -c alembic.ini upgrade head
```

Leave `LOREFORGE_DATABASE_MIGRATIONS_ENABLED=false` unless you intentionally want
application startup to run migrations.

## Run

```powershell
uv run --locked uvicorn loreforge.main:app --app-dir src
```

Run the frontend:

```powershell
cd frontend
npm run dev
```

Useful local endpoints:

- `GET /health`
- `GET /ready`
- `GET /metrics`
- `GET /docs`

## Test

```powershell
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src
git diff --check
```

Frontend checks:

```powershell
cd frontend
npm run typecheck
npm test
npm run lint
npm run build
```

Default tests are offline. Live Gemini and live database smoke tests are opt-in.

## Evaluate

Passing baseline:

```powershell
uv run --locked python -m loreforge.evaluation --dataset tests/fixtures/evaluation/golden_dataset.json --thresholds tests/fixtures/evaluation/thresholds.json --output .tmp/evaluation-golden-report.json --human
```

Intentional regression proof:

```powershell
uv run --locked python -m loreforge.evaluation --dataset tests/fixtures/evaluation/degraded_dataset.json --thresholds tests/fixtures/evaluation/thresholds.json --output .tmp/evaluation-degraded-report.json --human
```

Exit codes:

- `0`: pass
- `1`: quality regression
- `2`: configuration/setup error

## Troubleshooting

`/ask` returns `503`:

- Expected when providers are disabled or no evidence is indexed.
- Configure query embeddings, reranker, LLM provider, and indexed evidence for a
  live AskMe run.

`/ready` returns `503`:

- Application lifespan may not have started.
- Database health may be failing when `LOREFORGE_DATABASE_URL` is configured.

Tests skip live smoke checks:

- Expected unless `LOREFORGE_RUN_LIVE_GEMINI_SMOKE=true` or
  `LOREFORGE_RUN_LIVE_DATABASE_SMOKE=true`.

Provider model downloads are slow:

- Local Sentence Transformers and reranker models load only when explicitly
  configured. Default tests should not load them.

Docker build is slow or times out:

- Current Day 37 Docker implementation is present, but final Docker build
  verification remains pending due dependency-download network conditions.

`git diff --check` prints LF-to-CRLF warnings:

- Treat actual whitespace errors as failures. The current warning for
  `tests/test_settings.py` is a Git line-ending warning, not a diff whitespace
  failure.
