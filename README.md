# LoreForge

LoreForge is a Python 3.13 backend and React frontend foundation for a production-minded retrieval-augmented
assistant named AskMe. It is a public portfolio project focused on enterprise
RAG engineering: ingestion, retrieval, grounded generation, citation
enforcement, evaluation, observability, persistence, authentication, and
reproducible local development.

The project is local-first and zero-cost by default. It starts without provider
secrets, avoids live model calls during normal tests, and documents incomplete
production areas instead of hiding them.

## Problem Statement

Enterprise RAG systems fail in ways that ordinary API tests do not catch:

- documents are parsed or chunked incorrectly
- retrieval misses relevant evidence
- generated answers cite unsupported sources
- ownership boundaries leak documents across users
- provider failures expose unsafe details
- quality regresses without visible HTTP errors

LoreForge exists to demonstrate how to build and verify these boundaries in a
small, inspectable backend.

## Key Capabilities

Implemented and tested:

- FastAPI application with `/health`, `/ready`, `/metrics`, admin, document, and
  AskMe routes
- PDF upload validation, page-aware parsing, deterministic normalization, and
  citation-aware chunking
- ingestion-to-index orchestration with rollback behavior
- document catalog, indexing state, user, ownership, chunk, embedding, and
  retrieval metadata contracts
- PostgreSQL persistence via SQLAlchemy and Alembic migrations
- API-key bearer authentication and ownership isolation
- embedding provider contracts, local Sentence Transformers provider, and Gemini
  embedding provider
- in-memory vector index and BM25 lexical index
- hybrid retrieval with Reciprocal Rank Fusion
- cross-encoder reranking contract and local provider
- grounded evidence context, prompt construction, provider-independent
  generation, Gemini generation, OpenRouter adapter, citation extraction, and
  citation enforcement
- production query composition engine
- request IDs, structured request logging, readiness checks, and in-process
  metrics
- deterministic offline evaluation framework with regression thresholds and CLI
- Dockerfile, `.dockerignore`, and Docker Compose configuration

Default behavior:

- providers are disabled
- auth is disabled unless configured
- PostgreSQL is disabled unless `LOREFORGE_DATABASE_URL` is set
- `/ask` returns `503` until providers and indexed evidence are configured
- live Gemini and database smoke tests are skipped unless explicitly enabled

## Architecture Summary

```text
FastAPI adapters
  -> application container and services
  -> LoreForge-owned protocols and core workflows
  -> infrastructure adapters
  -> provider/database libraries
```

Core workflows are framework-independent where practical. FastAPI handles
transport concerns; application services and provider/repository protocols carry
the backend behavior.

See [docs/architecture.md](docs/architecture.md) for request, ingestion,
retrieval, evaluation, and observability lifecycle diagrams.

## Technology Stack

- Python 3.13
- FastAPI and Uvicorn
- uv
- SQLAlchemy, Alembic, PostgreSQL via psycopg
- pypdf
- Sentence Transformers
- Gemini through `google-genai`
- pytest
- Ruff
- mypy
- Docker and Docker Compose packaging
- React, TypeScript, Vite, React Router, TanStack Query, React Hook Form, Zod, Vitest, and React Testing Library

See [docs/dependencies.md](docs/dependencies.md) for the dependency audit.

## Project Structure

```text
frontend/         React product shell, route architecture, API client foundation, and UI tokens
src/loreforge/
  api/              FastAPI transport routes
  application/      application container and composition root
  askme/            framework-independent AskMe service contract
  auth/             user identity, auth protocols, API-key authenticator
  catalog/          document lifecycle and ownership metadata
  database/         SQLAlchemy models, repositories, engine lifecycle
  documents/        upload, parsing, normalization, chunking, ingestion
  embeddings/       embedding contracts, local provider, Gemini provider
  evaluation/       deterministic offline quality regression framework
  generation/       evidence, prompts, generation providers, citations
  indexing/         ingestion-to-index orchestration
  observability/    request context, traces, metrics, provider adapters
  query/            production grounded-query composition engine
  reranking/        reranker contracts and local provider
  retrieval/        BM25, vector, hybrid/RRF, durable retrieval support
  vector_index/     in-memory vector index and similarity

migrations/         Alembic migrations
tests/              offline test suite and deterministic fixtures
docs/               engineering documentation
```

## Local Development

Install dependencies:

```powershell
uv sync --all-groups
```

Run the API:

```powershell
uv run --locked uvicorn loreforge.main:app --app-dir src
```

Useful endpoints:

- `GET /health`
- `GET /ready`
- `GET /metrics`
- `GET /docs`

Run the frontend foundation:

```powershell
cd frontend
npm install
npm run dev
```

Frontend checks:

```powershell
npm run typecheck
npm test
npm run lint
npm run build
```

For a fuller handoff path, see [docs/onboarding.md](docs/onboarding.md) and
[docs/frontend.md](docs/frontend.md).

## Configuration

Configuration is centralized in `src/loreforge/settings.py` and documented in
`.env.example`.

Copy the template only for local overrides:

```powershell
Copy-Item .env.example .env
```

Important defaults:

- `LOREFORGE_ENVIRONMENT=development`
- provider selections are `disabled`
- `LOREFORGE_DATABASE_URL` is empty
- `LOREFORGE_AUTH_PROVIDER=disabled`
- live smoke tests are disabled

Production mode requires `LOREFORGE_PUBLIC_BASE_URL` and rejects debug logging.

See [docs/configuration.md](docs/configuration.md).

## Database and Migrations

Leave `LOREFORGE_DATABASE_URL` empty for in-memory local startup.

When PostgreSQL is configured:

```powershell
uv run --locked alembic -c alembic.ini upgrade head
```

See [docs/postgresql-persistence.md](docs/postgresql-persistence.md).

## Testing

Run the full deterministic suite:

```powershell
uv run --locked pytest
```

Run static checks:

```powershell
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src
git diff --check
```

Live provider/database smoke tests are opt-in and skipped by default.

## Evaluation

Passing deterministic quality gate:

```powershell
uv run --locked python -m loreforge.evaluation --dataset tests/fixtures/evaluation/golden_dataset.json --thresholds tests/fixtures/evaluation/thresholds.json --output .tmp/evaluation-golden-report.json --human
```

Intentional degraded gate:

```powershell
uv run --locked python -m loreforge.evaluation --dataset tests/fixtures/evaluation/degraded_dataset.json --thresholds tests/fixtures/evaluation/thresholds.json --output .tmp/evaluation-degraded-report.json --human
```

Exit codes:

- `0`: pass
- `1`: quality regression
- `2`: configuration/setup error

See [docs/evaluation.md](docs/evaluation.md).

## Observability

LoreForge includes:

- `X-Request-ID` correlation
- request-local observability context
- structured request logs
- `/metrics` JSON snapshot
- HTTP, readiness, retrieval, indexing, and provider-operation metrics

Logs and metrics avoid secrets, prompts, full questions, answers, raw document
text, vectors, provider payloads, filenames, request IDs as metric labels, user
IDs as metric labels, and document IDs as metric labels.

See [docs/observability.md](docs/observability.md).

## Deployment

Dockerfile, `.dockerignore`, and Docker Compose configuration are present.

Day 37 Docker implementation is complete, but final Docker image build
verification remains pending because locked dependency downloads timed out under
current network conditions. This is documented as a known limitation rather than
claimed as verified.

See [docs/deployment.md](docs/deployment.md).

## Production Readiness

See [docs/production-readiness-checklist.md](docs/production-readiness-checklist.md)
for completed, partial, pending, and future items across security, retrieval,
persistence, observability, evaluation, deployment, testing, and documentation.

## Demo and Interview Guides

- [docs/demo-guide.md](docs/demo-guide.md)
- [docs/interview-guide.md](docs/interview-guide.md)
- [docs/final-engineering-audit.md](docs/final-engineering-audit.md)

## Known Limitations

- Default `/ask` is unavailable until providers and evidence are configured.
- Docker build verification remains pending due network dependency-download
  conditions.
- No CI workflow is committed yet.
- Metrics are in-process and reset on restart.
- No external metrics collector, dashboards, alerts, or distributed tracing.
- Uploaded PDF bytes are not durably stored.
- Runtime vector and BM25 indexes are in memory and need a rebuild strategy after
  restart.
- Evaluation is deterministic fixture mode, not live provider/database quality
  evaluation.
- No OAuth/OIDC, roles, RBAC, or rate limiting.
- Frontend workflows are shell-level until the authenticated data layer is connected.
- No Kubernetes or cloud-specific deployment manifests.

## Roadmap

Near term:

- Add CI with pytest, Ruff, mypy, diff check, and evaluation gate.
- Verify Docker build in a stable network environment.
- Add focused rebuild/runbook docs for in-memory retrieval state.

Mid term:

- Durable uploaded-file storage.
- Background indexing workers and retry/idempotency controls.
- External metrics export and dashboards.
- Expanded golden evaluation set with human-reviewed cases.

Long term:

- OIDC/JWT enterprise identity provider integration.
- Durable vector/BM25 retrieval backend or rebuildable retrieval service.
- Production deployment runbooks and backup/restore procedures.
- Optional model-assisted evaluation alongside deterministic gates.
