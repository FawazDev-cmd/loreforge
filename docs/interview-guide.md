# Interview Guide

This guide summarizes the engineering decisions behind LoreForge and prepares
concise answers for technical review.

## Core Engineering Decisions

Why FastAPI?

- It gives a small ASGI presentation layer with clear request/response models.
- It is mature enough for production-style APIs without dominating the core
  architecture.

Why Clean Architecture?

- RAG systems change providers, indexes, prompts, and persistence strategies.
- Keeping core workflows framework-independent makes those changes safer.

Why `uv`?

- It gives reproducible dependency resolution and fast local workflows.

Why PostgreSQL?

- Durable metadata, ownership, indexing state, chunks, and embeddings need a
  relational foundation before adding more production behaviors.

Why in-memory vector/BM25 indexes still exist?

- They keep the local vertical slice simple and deterministic. Durable retrieval
  metadata exists, but production-grade vector/BM25 persistence and rebuild
  strategy remain future work.

Why deterministic evaluation instead of an LLM judge?

- A deterministic gate is cheap, repeatable, offline, and suitable for CI. LLM
  judging can be added later as an optional layer, not the baseline.

## Tradeoffs

- Local-first defaults reduce cost and risk but require explicit configuration
  for live RAG demos.
- Provider abstractions add some indirection but prevent Gemini/OpenRouter/local
  details from leaking into core workflows.
- In-process metrics are easy to test and safe for local deployments, but they do
  not replace external monitoring.
- API-key auth is intentionally minimal. It proves ownership boundaries without
  pretending to be a full identity platform.

## Common Architecture Questions

How does a request reach core logic?

- FastAPI validates transport input, resolves auth/container dependencies, and
  calls application services. Core services receive typed values, not request
  objects.

Where are secrets read?

- Through typed settings at composition boundaries. Core modules do not read
  environment variables.

What happens when `/ask` lacks evidence?

- The query engine raises a safe no-evidence error. The LLM is not asked to
  answer without citation-ready evidence.

How is cross-user access prevented?

- Ownership is stored with document metadata and enforced in catalog/indexing and
  retrieval paths. Cross-owner access is denied or returned as not found.

## Common Scaling Questions

What would you change for more documents?

- Add durable vector/BM25 indexes or a rebuildable retrieval store.
- Add background indexing workers.
- Persist uploaded document bytes.
- Add queueing, retries, and idempotency keys.

What would you change for production observability?

- Export the existing low-cardinality metrics to Prometheus or OpenTelemetry.
- Add dashboards and alerts.
- Add distributed tracing at service boundaries.

What would you change for enterprise auth?

- Add JWT/OIDC validation behind the existing auth boundary.
- Add organization/role models only when product requirements justify them.

What would you change for higher answer quality?

- Expand evaluation cases.
- Add human-reviewed golden sets.
- Add optional LLM judging.
- Tune retrieval/reranking only against tracked metrics, not ad hoc examples.

## Expected Reviewer Concerns

Docker build is not fully verified.

- Correct. The files exist, but final build verification remains pending because
  dependency downloads timed out. The limitation is documented rather than hidden.

Default `/ask` can return `503`.

- Correct. LoreForge starts safely without secrets or live providers. Live RAG
  requires explicit provider and evidence configuration.

Evaluation is fixture mode.

- Correct. It is a deterministic CI baseline, not a replacement for live
  production evaluation or human review.
