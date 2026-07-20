> Historical note: this audit captured Day 31 gaps at the time it was written. Several items listed here, including settings, authentication, ownership, PostgreSQL, Docker packaging, observability, and evaluation, were implemented in later milestones. Use `README.md`, `.ai/current_state.md`, and `docs/production-readiness-checklist.md` for current status.

# Production Gap Audit

Day 34 status note: this audit was written before the PostgreSQL persistence milestone. Catalog and indexing-attempt metadata now have SQLAlchemy/PostgreSQL adapters and Alembic migrations; semantic vector retrieval, BM25 retrieval, original document storage, metrics, and query observations remain non-durable.

Day 31 audit date: 2026-07-18

This audit documents the inspected repository state for LoreForge after the deterministic backend foundation and before the production-backend phase. It is not an implementation plan disguised as completed work. LoreForge is not production-complete today.

## 1. Executive Summary

LoreForge can currently run a deterministic FastAPI backend for a local-first RAG vertical slice. It supports PDF validation, parsing, normalization, chunking, in-memory cataloging, in-memory semantic and lexical indexing, hybrid retrieval, reranking, grounded prompt construction, provider-independent generation, citation enforcement, evaluation primitives, observability primitives, admin routes, document upload/indexing routes, and an AskMe route.

The verified end-to-end RAG path is deterministic and offline-only in tests. It uses injected fake or local-boundary providers rather than live user traffic, durable databases, persistent file storage, or authenticated access.

Real authenticated users cannot use LoreForge safely today because there is no settings layer, no environment-file workflow, no automatic provider wiring, no authentication, no authorization, no users, no ownership model, no durable document storage, no durable indexes, no database, no migrations, no Docker configuration, no CI workflow, and no deployment configuration.

Durable production operation is blocked by in-memory runtime state. Catalog entries, vector index contents, BM25 corpus state, query observations, and uploaded PDF bytes are lost on process restart. There is no job recovery, no transaction boundary across catalog/index/file operations, and no persistent audit/query history.

Reusable production architecture already exists and should be retained: immutable domain models, service boundaries, provider protocols, deterministic document processing, retrieval algorithms, reranking pipeline, prompt/evidence construction, citation validation, evaluation helpers, observability models, application container/composition root, API schemas, and deterministic tests.

## 2. Current Runtime Inventory

### Application Startup

- `src/loreforge/main.py` defines `create_app(...)` and module-level `app`.
- Startup uses a FastAPI lifespan handler to set `application.state.container` from `create_application_container()`.
- `FastAPI(title="LoreForge", version="0.1.0")` is configured.
- Routers registered: `admin_router`, `askme_router`, and `documents_router`.
- `GET /health` returns `{"status": "healthy", "service": "loreforge"}`.

### Dependency Composition

- `src/loreforge/application/composition.py` owns service construction.
- `create_application_container(...)` creates one isolated runtime container per application instance.
- Default container state:
  - `CatalogService(InMemoryCatalogRepository())`
  - `InMemoryVectorIndex()`
  - `InMemoryBM25Index()`
  - `InMemoryMetricsRecorder()`
  - `DocumentIndexingService(...)`
  - `AskMeService` backed by `UnavailableGroundedQueryEngine` unless provider factories are supplied
- `CompositionFactories` can inject document ingestor, document embedding provider, query embedding provider, reranker provider, LLM provider, custom AskMe service, or custom document indexing service.
- There is no environment-driven composition root.

### API Routes

- `src/loreforge/api/documents.py`
  - `POST /documents/upload`
  - Validates a PDF upload boundary and returns accepted metadata.
  - Does not persist bytes or index the document.
- `src/loreforge/api/admin.py`
  - `GET /admin/documents`
  - `GET /admin/documents/{document_id}`
  - `POST /admin/documents`
  - `POST /admin/documents/{document_id}/index`
  - `POST /admin/documents/{document_id}/ingesting`
  - `POST /admin/documents/{document_id}/ready`
  - `POST /admin/documents/{document_id}/failed`
  - `POST /admin/documents/{document_id}/deleted`
- `src/loreforge/api/askme.py`
  - `POST /ask`
  - Returns 503 by default when no production query engine is wired.

All endpoints are public today.

### Document Registration

- `CatalogEntry` and `DocumentStatus` live in `src/loreforge/catalog/models.py`.
- `CatalogService` in `src/loreforge/catalog/service.py` enforces lifecycle transitions.
- `CatalogRepository` protocol and `InMemoryCatalogRepository` live in `src/loreforge/catalog/repository.py`.
- Document registration stores metadata only, not file bytes.

### PDF Handling

- `src/loreforge/documents/upload.py` validates filename, media type, size, and PDF signature.
- `MAX_UPLOAD_SIZE_BYTES` is 10 MiB.
- Filenames are reduced to basename with slash/backslash normalization.
- `src/loreforge/documents/parsing.py` parses PDF bytes with `pypdf`.
- Upload bytes are read into memory by API routes using `await file.read(MAX_UPLOAD_SIZE_BYTES + 1)`.
- No local file path or durable object storage is used.

### Indexing

- `DocumentIndexingService` in `src/loreforge/indexing/service.py` validates the PDF, marks the catalog entry `INGESTING`, ingests and chunks the document, embeds chunks, adds chunks to the shared vector and BM25 indexes, and marks the catalog entry `READY`.
- If indexing fails after chunks are known, it rolls back vector and BM25 entries for those chunk IDs and marks the catalog entry `FAILED` where possible.
- If no embedding provider is supplied, indexing is unavailable.
- No job queue, durable job record, or idempotency key exists.

### Semantic Retrieval

- `InMemoryVectorIndex` in `src/loreforge/vector_index/memory.py` stores `IndexedVector` values in a dict keyed by chunk UUID.
- Search performs exact cosine similarity with deterministic tie-breaking by chunk UUID.
- Empty index search raises `VectorIndexError`.
- No pgvector or external vector database exists.

### Lexical Retrieval

- `InMemoryBM25Index` in `src/loreforge/retrieval/bm25.py` stores chunks, term frequencies, document lengths, document frequencies, and average document length in memory.
- Search uses deterministic BM25 scoring and tie-breaking.
- Empty index search raises `BM25IndexError`.
- No durable lexical index or PostgreSQL-backed full-text index exists.

### Reranking

- `RerankerProvider` protocol lives in `src/loreforge/reranking/provider.py`.
- `LocalCrossEncoderReranker` in `src/loreforge/reranking/local.py` is a lazily loaded local Sentence Transformers adapter.
- `rerank_hybrid_results(...)` is used by `ProductionGroundedQueryEngine`.
- Default application startup does not instantiate the local reranker.

### Generation

- `LLMProvider` protocol lives in `src/loreforge/generation/provider.py`.
- `GenerationRequest` contains system prompt, user prompt, max output tokens, and temperature.
- `GenerationResponse` contains text, model, and finish reason.
- `OpenRouterLLMProvider` and `OpenRouterConfig` live in `src/loreforge/generation/openrouter.py`.
- The OpenRouter adapter uses a configurable HTTPS base URL and timeout, but it is not wired by default.
- No Gemini adapter exists.
- No OpenAI adapter exists.

### Citations

- Citation extraction and validation live in `src/loreforge/generation/citations.py`.
- `validate_grounded_answer(...)` enforces citation presence and source support.
- `ValidatedGroundedAnswer` lives in `src/loreforge/generation/validation_models.py`.
- `AskMeService` rejects unvalidated or source-less answers.

### Evaluation

- `src/loreforge/evaluation/` contains deterministic evaluation primitives for retrieval metrics, citation metrics, answer normalization, case evaluation, and report aggregation.
- Retrieval metrics require ground-truth relevant chunk IDs and remain offline benchmark tools.
- Runtime query observation reuses citation-ID evaluation only where deterministic inputs exist.

### Observability

- `src/loreforge/observability/` contains `RequestTracer`, `RequestTrace`, `StageMetric`, `RuntimeQueryObservation`, `InMemoryMetricsRecorder`, clocks, and latency summaries.
- Configured `ProductionGroundedQueryEngine` records one trace per query when a metrics recorder is injected.
- Observability records safe metadata only: counts, stage timings, provider model, finish reason, citation status, and failure category.
- No external metrics exporter or persistent trace sink exists.

### Failure Handling

- API routes map internal service failures to safe HTTP responses.
- AskMe maps no-evidence/composition failures to safe grounding/unavailable errors.
- Indexing maps raw upload/provider failures to safe API details and attempts index rollback.
- There is no durable recovery from process crash during indexing.

## 3. Configuration and Secret Management

Inspected facts:

- `.env` does not exist in the repository.
- `.env.example` does not exist in the repository.
- `.gitignore` ignores `.env` and `.env.*`.
- No `pydantic-settings` dependency exists in `pyproject.toml`.
- No `BaseSettings` usage was found.
- No `os.getenv` usage was found.
- No `os.environ` usage was found in source.
- No environment variables are currently read by the application.
- No provider is automatically enabled by environment variables or startup configuration.
- Secrets can currently enter the application only by manually constructing provider configs in Python and injecting providers through `CompositionFactories`.
- Startup validation exists for object types inside `ApplicationContainer`, but not for environment variables or deployment settings.

Day 32 exact gaps:

- Add a typed settings layer.
- Add `.env.example` with placeholder names only.
- Define environment variable names for provider keys, model names, host/runtime mode, CORS policy, database URL, storage configuration, and auth settings.
- Keep `.env` ignored.
- Add startup validation for required settings in production mode.
- Preserve degraded local startup when production settings are absent.
- Document human secret provisioning steps without committing secrets.

## 4. Provider Integration Inventory

### Contract Exists

- Embedding document batches: `EmbeddingProvider` in `src/loreforge/embeddings/provider.py`.
- Query embeddings: `QueryEmbeddingProvider` in `src/loreforge/embeddings/provider.py`.
- Reranking: `RerankerProvider` in `src/loreforge/reranking/provider.py`.
- Generation: `LLMProvider` in `src/loreforge/generation/provider.py`.

### Adapter Exists

- Local Sentence Transformers embedding adapter: `LocalSentenceTransformerProvider`.
- Local Sentence Transformers cross-encoder reranker: `LocalCrossEncoderReranker`.
- OpenRouter chat-completions adapter: `OpenRouterLLMProvider`.

### Fake or Deterministic Providers

- Tests use fake embedding, reranking, and LLM providers.
- Day 28/29 integration tests prove the HTTP vertical slice with deterministic provider fakes.

### OpenRouter, OpenAI, Gemini, Local

- OpenRouter: adapter exists, tests use injected fake transport, not live network.
- OpenAI: no adapter found.
- Gemini: no adapter found.
- Local: embedding and reranking adapters exist and lazily load Sentence Transformers models when used.

### Provider Metadata Contracts

- `GenerationResponse` exposes `model` and `finish_reason` only.
- Token usage is not represented in the generation contract.
- Runtime observations record model and finish reason when supplied.
- Embedding result metadata includes model and dimensions in `EmbeddingResult`.

### Retry and Timeout Behavior

- OpenRouter config includes `timeout_seconds`, default `30.0`.
- OpenRouter transport passes timeout to `urlopen`.
- No retry policy was found.
- No rate-limit-specific handling was found.

### Provider Error Translation

- OpenRouter wraps HTTP, network, decoding, JSON, and malformed payload failures as `OpenRouterGenerationError` with generic messages.
- Local embedding wraps load/inference failures as `LocalEmbeddingError`.
- Local reranking wraps load/inference/malformed-score failures as `LocalRerankingError`.
- Query engine wraps unexpected collaborator errors as `QueryExecutionError`.
- AskMe maps query errors to safe `AskMeGroundingError` or `AskMeUnavailableError`.

### Runtime Wiring and Live Verification

- Runtime provider wiring exists only through Python injection via `CompositionFactories`.
- Default app does not wire any live provider.
- No live OpenRouter verification was found.
- No Gemini live verification exists because no Gemini adapter exists.

Day 33 exact work:

- Add Gemini embedding and generation adapters behind existing provider protocols.
- Extend settings from Day 32 to configure Gemini keys/model names/timeouts.
- Decide whether Gemini replaces or complements OpenRouter/local providers.
- Add fake transport/client tests and optional live smoke-test documentation.
- Do not couple core query/indexing logic to Gemini-specific classes.

## 5. Persistence Inventory

### In Memory

- Catalog entries: `InMemoryCatalogRepository`.
- Vector embeddings/indexed chunks: `InMemoryVectorIndex`.
- BM25 chunks and statistics: `InMemoryBM25Index`.
- Metrics/traces: `InMemoryMetricsRecorder`.
- Application dependencies: `ApplicationContainer` per app instance.
- PDF upload bytes: held in memory for request processing only.

### Local File Based

- No application file storage was found.
- No document/chunk/index/evaluation/trace persistence to local files was found.

### Temporary

- FastAPI/Starlette may handle multipart uploads internally, but LoreForge code reads bytes and closes `UploadFile`.
- No LoreForge-owned temporary file path or cleanup routine exists.

### Durable

- No durable application state exists.
- No database, migration, object storage, or persistent vector store exists.

### Reconstructed on Startup

- Empty catalog, empty vector index, empty BM25 index, empty metrics recorder, and degraded AskMe service are created on default startup.
- No startup reconstruction from documents, database, or disk exists.

### Lost on Restart

- Registered documents.
- Document statuses.
- Parsed/chunked content.
- Embeddings.
- Vector index state.
- BM25 index state.
- Indexing job progress.
- Query observations.
- Evaluation results.
- Uploaded PDF bytes.

### Existing Repository Abstractions

- `CatalogRepository` protocol exists.
- No document repository abstraction exists.
- No chunk repository abstraction exists.
- No embedding repository abstraction exists.
- No query history repository abstraction exists.
- No metrics repository abstraction exists beyond `MetricsRecorder` protocol.
- No file storage abstraction exists.

### Missing Database/Migration/Transaction Boundaries

- No SQLAlchemy, Alembic, PostgreSQL, SQLite, pgvector, or database URL usage found.
- No migrations folder exists.
- No database transaction boundary exists around document registration, file storage, chunk storage, embedding storage, and index updates.
- Indexing rollback is best-effort in memory and cannot recover from process crash.

Day 34 exact work:

- Add PostgreSQL database integration and migrations.
- Model catalog/document/chunk/indexing job state.
- Preserve existing domain models where possible.
- Introduce transaction boundaries for catalog and ingestion metadata.
- Keep tests isolated with a test database or repository fakes.

Day 35 exact work:

- Add durable hybrid retrieval: persisted embeddings, pgvector search, durable lexical/BM25 or database-backed lexical retrieval, and reconstruction strategy.
- Keep current retrieval contracts and algorithms as reference behavior.
- Add restart durability tests.

## 6. Authentication and Authorization Inventory

Inspected status:

- No users model found.
- No sessions found.
- No JWT validation found.
- No API-key dependency found.
- No bearer-token dependency found.
- No roles found.
- No authorization layer found.
- No document ownership model found.
- No user-scoped retrieval found.
- No tenant isolation found.
- No administrative access controls found.

Public endpoints today:

- `GET /health`
- `POST /documents/upload`
- `GET /admin/documents`
- `GET /admin/documents/{document_id}`
- `POST /admin/documents`
- `POST /admin/documents/{document_id}/index`
- `POST /admin/documents/{document_id}/ingesting`
- `POST /admin/documents/{document_id}/ready`
- `POST /admin/documents/{document_id}/failed`
- `POST /admin/documents/{document_id}/deleted`
- `POST /ask`

Day 36 exact work:

- Add authenticated principal model.
- Add FastAPI dependencies for auth validation.
- Add ownership fields to durable document/catalog records.
- Restrict admin mutation endpoints.
- Scope retrieval to authorized documents.
- Add tests for anonymous, unauthorized, and authorized access.

## 7. File Storage Inventory

Current PDF handling:

- `/documents/upload` reads bytes, validates them, returns metadata, and discards bytes.
- `/admin/documents/{document_id}/index` reads bytes, passes them through indexing, and discards bytes after request processing.
- No uploaded PDF bytes are persisted by LoreForge.
- No local file paths are stored.
- No storage abstraction exists.
- No storage ownership exists.
- Documents do not survive restart as files.
- Chunks survive only in memory until restart.

Temporary-file behavior:

- LoreForge code does not create temporary files.
- LoreForge code does not implement temp-file deletion because it does not own temp files.

Day 37 exact work:

- Add a storage abstraction for original document bytes.
- Add Supabase Storage or equivalent implementation behind that abstraction.
- Store object key/path metadata in the durable database.
- Enforce owner-scoped storage access.
- Add cleanup behavior for failed indexing and deleted documents.
- Add tests for storage write/read/delete failures.

## 8. Operational Inventory

### Health Endpoint

- `GET /health` exists and returns a static healthy payload.
- It does not check database, storage, provider availability, or index readiness.

### Degraded Startup

- Default startup is import-safe and does not load models or read credentials.
- Default `/ask` returns 503 because `UnavailableGroundedQueryEngine` is used when providers are not configured.

### Logging

- No application logging infrastructure was found.
- No structured logger setup was found.

### Tracing and Metrics

- In-memory tracing and metrics models exist.
- No external exporter exists.
- No public/admin metrics endpoint exists.

### Error Responses

- API routes map common failures to safe HTTP errors.
- Some document upload endpoint validation details are returned directly from validation errors, but they are fixed validation strings from local code.
- No global exception handler was found.

### Startup and Shutdown Behavior

- Startup creates an `ApplicationContainer`.
- Shutdown has no explicit cleanup because no durable connections/resources are owned today.

### CORS

- No CORS middleware was found.

### Request Size Controls

- PDF upload reads at most `MAX_UPLOAD_SIZE_BYTES + 1` and validates size against 10 MiB.
- Other routes rely on FastAPI/Pydantic validation.

### Rate Limiting

- No rate limiting was found.

### Timeouts and Retries

- OpenRouter adapter has a per-request timeout.
- No application-level timeout policy was found.
- No retry policy was found.

### Background Work and Job Recovery

- No background job system exists.
- Indexing is performed in the request path.
- No job recovery exists.

### Idempotency

- No idempotency keys exist.
- Catalog duplicate document IDs are rejected.
- Indexing rejects already-ready documents, but upload/index retry semantics are not production-grade.

### Docker Status

- No `Dockerfile`, `compose.yaml`, `docker-compose.yml`, or container entrypoint exists.

### CI Status

- No `.github/workflows` files exist.

### Deployment Configuration

- No deployment configuration files exist.
- No host-specific configuration exists.

Days 38-40 exact work:

- Day 38: live end-to-end validation with real configured services and seeded non-sensitive test documents.
- Day 39: Docker and CI with the documented verification pipeline.
- Day 40: deployment and security hardening, including deployment config, CORS, rate limits, logging, production health/readiness, and secret handling checks.

## 9. Security Risks

| Severity | Risk | Evidence | Reason |
| --- | --- | --- | --- |
| Critical | Public admin mutation endpoints | `src/loreforge/api/admin.py` has no auth dependency | Anyone with network access could register, mutate, index, fail, or delete document catalog entries. |
| Critical | No ownership or tenant isolation | No users, owner fields, tenant model, or user-scoped retrieval found | Future multi-user retrieval would risk cross-user document exposure. |
| High | No durable secret/settings workflow | `.env` ignored but absent, no `.env.example`, no settings layer, no env reads | Production secrets would require ad hoc Python injection and lack startup validation. |
| High | No durable persistence | Catalog, indexes, and observations are in memory | Restart loses documents/indexes and can make user-facing state inconsistent. |
| High | No durable file storage | Uploaded PDFs are read into memory and discarded | Users cannot rely on documents surviving restart or reindex after failure. |
| High | No rate limiting | No rate-limit middleware or dependency found | Public upload and AskMe endpoints could be abused for CPU, memory, or provider-cost pressure once providers are live. |
| Medium | Request-path indexing | Indexing runs inside `POST /admin/documents/{id}/index` | Long PDF processing/model calls can tie up request workers and has no recovery if interrupted. |
| Medium | Health endpoint is shallow | `/health` returns static payload only | Deployment would appear healthy even if database, storage, or providers are unavailable. |
| Medium | No CORS policy | No CORS middleware found | Browser deployment behavior is undefined; future frontend integration could accidentally over- or under-expose APIs. |
| Medium | Provider prompt leaves process boundary when OpenRouter is used | `OpenRouterLLMProvider` sends system/user prompts to configured HTTPS API | Requires explicit user/company approval and data-handling controls before real documents are used. |
| Low | Upload validation details are exposed | `/documents/upload` returns fixed validation messages | Current messages are not secrets, but production should standardize error detail policy. |
| Low | No external observability sink | only `InMemoryMetricsRecorder` exists | Useful local traces vanish on restart and cannot support production incident analysis. |

No real secret values were found or included in this audit.

## 10. Reusable Architecture

Keep and extend these parts:

- Immutable document/catalog/retrieval/generation/evaluation/observability models.
- `CatalogRepository` protocol as the seed for a durable catalog repository.
- `CatalogService` lifecycle rules.
- PDF validation/parsing/normalization/chunking modules.
- `DocumentIndexingService` orchestration shape, with durable transaction/storage boundaries added later.
- Embedding, query embedding, reranking, and LLM provider protocols.
- `LocalSentenceTransformerProvider` and `LocalCrossEncoderReranker` for local/dev paths.
- OpenRouter adapter as an optional generation adapter, not as the only production path.
- In-memory vector and BM25 indexes as deterministic test/reference implementations.
- Hybrid retrieval and RRF algorithms.
- Reranking pipeline.
- Evidence-context and grounded prompt construction.
- Citation extraction/enforcement and validated answer models.
- Evaluation primitives for offline benchmarks and runtime-compatible citation signals.
- Observability models, tracer, clocks, and recorder protocol.
- Application container and composition root pattern.
- Existing FastAPI transport schemas, with auth dependencies added later.
- Deterministic tests and fake-provider infrastructure.

The production phase should extend this architecture rather than rewrite it wholesale.

## 11. Recommended Service Choices

These are fit assessments based on the current codebase, not implemented integrations and not claims about current vendor pricing or free-tier limits.

### Supabase PostgreSQL

- Problem solved: durable relational state for users, documents, catalog entries, chunks, indexing jobs, query history, and evaluation records.
- Fit: current catalog repository protocol can grow a database-backed implementation; application composition can inject it.
- Integration boundary: new infrastructure repository package plus settings-driven composition.
- Human configuration required: project creation, database URL, credentials, migration access, environment variables.
- Migration concern: keep SQL schema domain-agnostic so future company onboarding uses organization/document ownership data, not hard-coded company terms.

### pgvector

- Problem solved: durable semantic embedding search in PostgreSQL.
- Fit: can replace or complement `InMemoryVectorIndex` behind retrieval services while preserving vector search result contracts.
- Integration boundary: vector repository/index adapter and migration enabling pgvector extension.
- Human configuration required: database extension availability and embedding dimension decisions.
- Migration concern: embedding dimension/model changes require versioning and reindex strategy.

### Supabase Auth

- Problem solved: user identity, JWT validation source, and session/auth lifecycle.
- Fit: FastAPI dependencies can validate bearer tokens and produce an authenticated principal for services.
- Integration boundary: API dependency layer, user/ownership fields in database records, retrieval scoping.
- Human configuration required: auth project setup, JWT issuer/audience/secrets, callback/provider settings.
- Migration concern: avoid coupling core domain logic to Supabase-specific user claims.

### Supabase Storage

- Problem solved: durable original PDF storage.
- Fit: storage abstraction can be injected into indexing/upload workflows; database can store object keys and ownership.
- Integration boundary: document storage service/provider and admin/document APIs.
- Human configuration required: bucket creation, access policy, credentials, object naming policy.
- Migration concern: store provider-neutral object keys/metadata so storage can be moved later.

### Gemini Generation

- Problem solved: real LLM generation provider.
- Fit: implement behind existing `LLMProvider` and reuse `GenerationRequest`/`GenerationResponse`.
- Integration boundary: generation adapter plus settings/composition root.
- Human configuration required: API key/project/model selection and acceptable data-use review.
- Migration concern: keep provider-specific request/response handling inside adapter.

### Gemini Embeddings

- Problem solved: real query/document embeddings without local model loading.
- Fit: implement behind `EmbeddingProvider` and `QueryEmbeddingProvider`.
- Integration boundary: embeddings adapter plus indexing/query composition.
- Human configuration required: API key/project/model selection, embedding dimensions, and cost/data-use review.
- Migration concern: embedding dimensions and model version must be recorded for reindexing and future provider changes.

### Render or Equivalent Initial Host

- Problem solved: public deployment target for the backend.
- Fit: FastAPI/uvicorn app can be hosted once settings, database, storage, Docker/CI, and security hardening are in place.
- Integration boundary: deployment configuration, environment variables, startup command, health/readiness checks.
- Human configuration required: account/project setup, env vars, secrets, domain settings, database/storage connectivity.
- Migration concern: avoid host-specific assumptions in core application code.

## 12. Day 32-40 Implementation Map

### Day 32 - Settings and Secrets

- Scope: typed settings, env variable names, `.env.example`, startup validation modes, documentation.
- Likely files/modules: new `src/loreforge/settings.py` or `src/loreforge/application/settings.py`, `application/composition.py`, README/docs, tests for settings validation.
- Dependencies: none beyond current audit.
- Expected tests: env parsing, missing required production secrets, local degraded defaults, secret repr redaction.
- Human checkpoint: approve env variable names and secret provisioning workflow.
- Acceptance criteria: no secrets committed; default local startup unchanged; production mode fails fast when required settings are absent.

### Day 33 - Real Gemini Provider Integration

- Scope: Gemini LLM and embedding adapters behind existing provider protocols.
- Likely files/modules: new provider modules under `embeddings/` and `generation/`, composition wiring, tests with fake transports/clients.
- Dependencies: Day 32 settings.
- Expected tests: request mapping, response parsing, safe error handling, timeout handling, no secret leakage, configured composition.
- Human checkpoint: Gemini credentials, model names, data-use approval.
- Acceptance criteria: adapters work behind protocols; default tests remain offline; live smoke path documented separately.

### Day 34 - PostgreSQL and Migrations

- Scope: durable relational schema and migration workflow.
- Likely files/modules: database package, migration directory, catalog repository implementation, settings, tests.
- Dependencies: Day 32 settings.
- Expected tests: repository contract against test database or isolated DB fixture, migrations apply, lifecycle persistence.
- Human checkpoint: database project/URL and migration strategy approval.
- Acceptance criteria: catalog/document/chunk/job metadata survives restart; migrations are reproducible.

### Day 35 - Durable Hybrid Retrieval

- Scope: persistent vector embeddings and lexical retrieval state.
- Likely files/modules: vector index adapter, lexical retrieval adapter, retrieval composition, indexing persistence integration.
- Dependencies: Days 33 and 34.
- Expected tests: semantic search parity, lexical search parity, hybrid results after restart, model/dimension validation.
- Human checkpoint: pgvector availability and embedding dimension/model decision.
- Acceptance criteria: indexed documents are retrievable after application restart.

### Day 36 - Authentication and Ownership

- Scope: authenticated principal, ownership fields, endpoint protection, user-scoped retrieval.
- Likely files/modules: API dependencies, catalog/document DB models, services, tests.
- Dependencies: Day 34 durable documents and users/ownership schema.
- Expected tests: anonymous rejected, wrong owner rejected, owner allowed, admin policy, retrieval scoping.
- Human checkpoint: auth provider setup and role policy decisions.
- Acceptance criteria: mutation/read/retrieval routes enforce ownership and admin controls.

### Day 37 - Durable File Storage

- Scope: storage abstraction and durable PDF object storage.
- Likely files/modules: new storage package, indexing service integration, database object metadata, tests.
- Dependencies: Days 34 and 36.
- Expected tests: upload write/read/delete, failure cleanup, owner-scoped access, restart reindex support.
- Human checkpoint: storage bucket/project setup and access policy.
- Acceptance criteria: original PDFs survive restart and are associated with owner/document records.

### Day 38 - Live End-to-End Validation

- Scope: controlled live validation against configured providers, database, storage, and auth.
- Likely files/modules: integration test docs/scripts, optional marked live tests, README updates.
- Dependencies: Days 32-37.
- Expected tests: opt-in live smoke test, seeded non-sensitive PDF, authenticated upload/index/ask path.
- Human checkpoint: approve live cost/data use and provide test credentials.
- Acceptance criteria: documented live path passes without using private/confidential data.

### Day 39 - Docker and CI

- Scope: reproducible container and CI verification pipeline.
- Likely files/modules: `Dockerfile`, compose file if needed, `.github/workflows`, README/docs.
- Dependencies: Days 32-38 clarify runtime settings and services.
- Expected tests: container starts, health endpoint reachable, CI runs pytest/ruff/mypy.
- Human checkpoint: repository secrets for CI/live tests if any; hosting build assumptions.
- Acceptance criteria: clean CI on push/PR and local container run documented.

### Day 40 - Deployment and Security Hardening

- Scope: deployment configuration, security policy, operational readiness, final hardening.
- Likely files/modules: deployment docs/config, API middleware/dependencies, health/readiness, logging/observability integration.
- Dependencies: Days 32-39.
- Expected tests: production settings validation, CORS policy, rate-limit behavior if implemented, readiness failures, no secret leakage.
- Human checkpoint: host project, domains, env vars, CORS origins, auth/storage/database/provider credentials.
- Acceptance criteria: deployed backend is reachable, authenticated, durable, observable, and documented as production-ready within its stated limits.

## Schedule Dependency Findings

The proposed Day 32-40 order is valid. No inspected dependency conflict requires reordering.

Day 33 depends on Day 32 for safe provider secrets. Day 35 depends on Day 34 because durable retrieval requires persistent storage. Day 36 should come before Day 37 so stored files can be tied to owners. Day 38 should follow provider, persistence, auth, and storage work. Day 39 and Day 40 naturally follow a live validated backend.
