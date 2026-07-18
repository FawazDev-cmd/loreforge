# LoreForge

LoreForge is a Python 3.13, FastAPI-based backend for a production-minded retrieval-augmented assistant named AskMe. It is a public portfolio project focused on enterprise RAG engineering: ingestion, retrieval, grounded generation, citation enforcement, evaluation, observability, testing, and reproducible local development.

The backend is intentionally local-first and zero-cost by default. The application starts without secrets or live providers, exposes health/admin/document/AskMe API routes, and keeps `/ask` honestly degraded until concrete embedding, reranking, and LLM providers are injected.

## Current Capabilities

Implemented and verified:

- FastAPI application startup and `/health`
- PDF upload validation
- page-aware PDF parsing
- deterministic text normalization
- deterministic citation-aware chunking
- ingestion orchestration
- document embedding contracts and local Sentence Transformers provider
- in-memory vector index
- in-memory BM25 lexical index
- hybrid retrieval with Reciprocal Rank Fusion
- cross-encoder reranking contract and local provider
- grounded evidence-context and prompt construction
- provider-independent generation contract
- OpenRouter generation adapter
- citation extraction and enforcement
- validated grounded-answer models
- AskMe service and API route
- admin catalog API
- document indexing API that populates shared semantic and lexical indexes
- deterministic runtime observability for configured AskMe queries
- deterministic evaluation primitives
- offline integration tests for the configured RAG vertical slice

Not enabled by default:

- live LLM calls
- centralized typed settings and startup validation
- persistence across process restarts
- authentication or authorization
- Docker or CI execution files
- frontend UI

## Repository Structure

```text
src/loreforge/
  api/              FastAPI transport routes
  application/      application container and composition root
  askme/            framework-independent AskMe service contract
  catalog/          in-memory document lifecycle catalog
  documents/        upload validation, parsing, normalization, chunking, ingestion
  embeddings/       embedding models, provider protocol, local provider, pipeline
  evaluation/       deterministic offline/runtime-compatible evaluation helpers
  generation/       evidence, prompts, provider contracts, OpenRouter, citations
  indexing/         document ingestion-to-index orchestration
  observability/    traces, metrics recorder, clocks, summaries
  query/            production grounded-query composition engine
  reranking/        reranker models, provider protocol, local cross-encoder
  retrieval/        semantic, BM25, hybrid/RRF retrieval models and logic
  vector_index/     in-memory vector indexing and similarity

tests/              offline unit, service, API, and integration tests
docs/               focused design and workflow documentation
.ai/                ignored project context and milestone state
```

## Architecture

LoreForge keeps business logic framework-independent where practical. FastAPI routes are transport adapters that delegate to application services. Runtime state is owned by one immutable `ApplicationContainer` per application instance.

Default startup creates:

- `CatalogService` backed by `InMemoryCatalogRepository`
- shared `InMemoryVectorIndex`
- shared `InMemoryBM25Index`
- `DocumentIndexingService`
- shared `InMemoryMetricsRecorder`
- degraded `AskMeService` unless all query providers are supplied through `CompositionFactories`

Configured startup can inject:

- document embedding provider
- query embedding provider
- reranker provider
- LLM provider
- custom AskMe service or document indexing service for tests/deployments

The default app does not instantiate local models, read provider credentials, call OpenRouter, or make network requests during import/startup.

## Local Setup

Install `uv`, then create the environment:

```bash
uv sync --all-groups
```

For locked verification runs, use the commands in [Verification](#verification).

## Run the API

```bash
uv run uvicorn loreforge.main:app --app-dir src
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "service": "loreforge"
}
```

Interactive OpenAPI docs are available from FastAPI at `/docs` when the development server is running.

## Environment Variables and Provider Configuration

LoreForge now has one centralized typed settings layer in `loreforge.settings`. Runtime configuration is loaded through `load_settings()` and validated at application-container startup. Do not add scattered `os.getenv()` or duplicated parsing logic elsewhere in the codebase.

The default settings keep LoreForge local-first and zero-cost:

- environment: `development`
- provider selections: `disabled`
- storage provider: `local`
- authentication provider: `disabled`
- metrics recording: enabled in memory

Copy `.env.example` to `.env` for local experimentation, then fill only the values you need. `.env` and `.env.*` are ignored by git. Never commit real provider keys, database URLs, service-role keys, JWT secrets, or private deployment values.

Environment switching is configuration-driven with `LOREFORGE_ENVIRONMENT`:

- `development` for normal local work
- `testing` for deterministic test/runtime configuration
- `production` for deployed runtime settings

Production mode fails fast unless `LOREFORGE_PUBLIC_BASE_URL` is configured. Provider, storage, and auth secrets are required only when their corresponding provider is explicitly enabled.

Important provider behavior:

- Gemini settings are defined for future Day 33 adapters, but Gemini runtime is not implemented yet.
- OpenRouter settings are defined and the existing adapter remains available, but it is not automatically wired by default.
- Local embedding/reranking model names are configurable, but local models still load lazily only when their providers are explicitly constructed.
- The default `/ask` route still returns `503` until concrete query embedding, reranking, LLM providers, and indexed evidence are supplied through the composition root.

Key configuration groups documented in `.env.example`:

- application identity and environment
- API host, port, and future CORS origins
- logging controls
- provider selections and provider-specific placeholders
- PostgreSQL URL, pool sizing, and migration placeholders
- local/Supabase storage placeholders
- Supabase Auth/JWT placeholders
- observability toggles
## API Overview

### Health

`GET /health`

Purpose: confirm the FastAPI application is running.

Responses:

- `200` with service health payload.

### Document Upload Boundary

`POST /documents/upload`

Purpose: validate and accept a PDF upload boundary without indexing it.

Request: multipart PDF file.

Responses:

- `201` accepted upload metadata
- `400` invalid upload payload
- `413` upload exceeds size limit
- `415` unsupported media type or invalid PDF

### Admin Catalog

`GET /admin/documents`

Purpose: list catalog entries in insertion order.

Responses:

- `200` ordered document list
- `503` if application services are unavailable

`GET /admin/documents/{document_id}`

Purpose: fetch one catalog entry.

Responses:

- `200` document metadata
- `404` document not found
- `422` invalid UUID
- `503` if application services are unavailable

`POST /admin/documents`

Purpose: register document metadata before indexing.

Request JSON:

```json
{
  "filename": "example.pdf",
  "page_count": 0,
  "chunk_count": 0
}
```

Responses:

- `201` created catalog entry with `UPLOADED` status
- `422` validation failure
- `503` if application services are unavailable

`POST /admin/documents/{document_id}/index`

Purpose: ingest a registered PDF, create chunks, embed chunks, populate shared vector/BM25 indexes, and transition catalog status.

Request: multipart PDF file.

Responses:

- `200` indexed chunk counts
- `404` document not found
- `409` lifecycle does not allow indexing or document is already indexed
- `422` invalid PDF upload
- `503` indexing provider/runtime unavailable

Lifecycle helper routes:

- `POST /admin/documents/{document_id}/ingesting`
- `POST /admin/documents/{document_id}/ready`
- `POST /admin/documents/{document_id}/failed`
- `POST /admin/documents/{document_id}/deleted`

Purpose: exercise catalog lifecycle transitions through the API.

Responses:

- `200` updated document metadata
- `404` document not found
- `409` invalid lifecycle transition
- `422` validation failure

### AskMe

`POST /ask`

Purpose: answer a user question with a citation-validated grounded answer when the application has configured providers and indexed evidence.

Request JSON:

```json
{
  "question": "Which retrieval methods does LoreForge combine?"
}
```

Responses:

- `200` answer with source citations
- `422` blank or invalid question
- `502` a safely grounded answer could not be produced
- `503` AskMe is unavailable, including default degraded startup

Default runtime behavior: `/ask` returns `503` until query embedding, reranking, and LLM providers are injected and relevant documents are indexed.

## Indexing Workflow

A configured runtime can prove the backend vertical slice through these steps:

1. Register metadata with `POST /admin/documents`.
2. Index a PDF with `POST /admin/documents/{document_id}/index`.
3. The indexing service validates the PDF, parses pages, normalizes text, chunks content, embeds chunks, writes to the shared vector index, writes to the shared BM25 index, and marks the document `READY`.
4. If indexing fails after ingestion begins, semantic and lexical index writes are rolled back and the catalog entry is marked `FAILED`.

All indexing state is in memory today.

## AskMe Workflow

When configured, `POST /ask` follows this path:

```text
question
  -> query embedding
  -> semantic retrieval and BM25 retrieval
  -> Reciprocal Rank Fusion
  -> reranking
  -> evidence-context construction
  -> grounded prompt construction
  -> provider-independent answer generation
  -> citation enforcement
  -> API response
```

The runtime records safe observability metadata for configured query executions: trace ID, UTC start time, total latency, stage latencies, retrieval/evidence/citation counts, citation validity, provider model, finish reason, and safe failure category. It does not record raw prompts, raw evidence text, answer text, credentials, headers, or provider payloads.

## Testing

Run all tests:

```bash
uv run --locked pytest
```

The default test suite is offline and deterministic. Provider and integration boundaries use fakes or injected transports; tests must not require live model downloads, OpenRouter, network access, sleeps, or randomness.

## Linting and Type Checking

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src
```

Whitespace check before handoff:

```bash
git diff --check
```

## Verification

Expected local verification pipeline:

```bash
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src
git diff --check
```

## Docker Usage

There is currently no `Dockerfile`, compose file, or container entrypoint in the repository. Docker reproducibility is a planned future hardening step, not a verified current capability.

## CI Readiness

There is currently no CI configuration in the repository. A future CI workflow should run the same verification pipeline documented above:

- `uv run --locked pytest`
- `uv run --locked ruff check .`
- `uv run --locked ruff format --check .`
- `uv run --locked mypy src`

## Deployment Prerequisites

Before deploying beyond local development, add and verify:

- explicit provider configuration loading
- secret management outside source control
- production process management
- persistence for catalog/index state if restart durability is required
- authentication and authorization for admin/document endpoints
- Docker or equivalent reproducible runtime packaging
- CI verification gates
- operational logging policy and external metrics/export adapters if needed

## Known Limitations

- Runtime catalog, vector index, BM25 index, and metrics recorder are in memory only.
- Default `/ask` is intentionally unavailable without injected providers.
- Local embedding/reranking providers may download or load model artifacts when used outside the default app.
- OpenRouter exists as an adapter but is not wired by default and requires explicit credentials/configuration.
- No authentication or authorization is implemented.
- No persistent document storage is implemented.
- No Docker or CI files are present.
- Evaluation primitives are deterministic, but benchmark retrieval quality still requires ground-truth evaluation cases.