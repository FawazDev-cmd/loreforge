# Production Readiness Checklist

Status labels:

- Complete: implemented and covered by tests or documentation.
- Partial: implemented with known deployment/runtime limitations.
- Pending: not implemented.

## Security

- Complete: API-key bearer authentication.
- Complete: user ownership model and same-owner access enforcement.
- Complete: cross-owner document access denial without resource-existence leak.
- Complete: secret-safe logging and metrics tests.
- Pending: OAuth/JWT provider integration.
- Pending: roles, RBAC, or organization-level permissions.
- Pending: rate limiting and abuse protection.

## Retrieval and Generation

- Complete: PDF ingestion, parsing, normalization, chunking.
- Complete: document and query embedding provider contracts.
- Complete: Gemini provider adapters.
- Complete: BM25, vector retrieval, hybrid RRF, reranking, grounded prompt,
  provider-independent generation, citation enforcement.
- Partial: semantic and BM25 runtime indexes are in-memory.
- Pending: durable vector/BM25 index rebuild strategy.
- Pending: streaming responses or conversation memory.

## Persistence

- Complete: PostgreSQL connectivity and Alembic migrations.
- Complete: durable document metadata, indexing state, users, ownership, chunks,
  embeddings, and retrieval metadata.
- Partial: uploaded PDF bytes are not durably stored.
- Pending: backup and restore runbook.

## Observability

- Complete: request ID propagation.
- Complete: structured request logs.
- Complete: `/metrics` in-process snapshot.
- Complete: HTTP, readiness, retrieval, indexing, and provider metrics.
- Partial: metrics reset on process restart.
- Pending: external metrics collector, dashboards, alerts, and distributed
  tracing.

## Evaluation

- Complete: deterministic offline evaluation fixture.
- Complete: retrieval, citation, groundedness, abstention, aggregation, and
  regression thresholds.
- Complete: CLI exit codes suitable for CI.
- Partial: fixture mode does not execute a live production provider/database
  stack.
- Pending: human review workflow and optional model judge.

## Deployment

- Complete: Dockerfile, `.dockerignore`, and Compose configuration are present.
- Partial: final Docker build verification remains pending due network
  dependency-download conditions.
- Pending: deployment platform runbook.
- Pending: Kubernetes manifests or cloud-specific IaC.

## Testing and CI

- Complete: large deterministic default test suite.
- Complete: Ruff and mypy verification.
- Complete: evaluation regression gate command.
- Pending: GitHub Actions or another CI workflow.

## Documentation

- Complete: README, onboarding, architecture, deployment, persistence, ingestion,
  observability, evaluation, dependency, demo, interview, and audit documents.
- Pending: generated API reference.
