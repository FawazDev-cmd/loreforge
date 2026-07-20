# Observability and Production Monitoring

LoreForge uses provider-neutral, in-process observability for local and portfolio
deployments. The current implementation is intentionally lightweight: it exposes
structured request logs, request correlation IDs, runtime health checks, query
traces, and a metrics snapshot without requiring a hosted monitoring vendor.

## Request Correlation

HTTP clients may send `X-Request-ID` with a UUID value. LoreForge preserves valid
UUIDs and returns the active request ID in the `X-Request-ID` response header. If
the header is missing or invalid, the API generates a new UUID.

The active request ID is stored in request-local context so downstream code can
read it without depending on FastAPI request objects. The context is reset after
each request.

## Request Logs

Request completion logs include only safe operational fields:

- `request_id`
- `method`
- `route`
- `status_code`
- `duration_ms`
- `authenticated`
- `error_category`

Logs must not include authorization headers, API keys, database URLs, prompts,
full questions, answers, raw document text, vectors, uploads, filenames, or user
IDs.

Startup, shutdown, and readiness failures are logged with generic messages. Raw
dependency exception details are not returned to clients.

## Metrics Snapshot

`GET /metrics` returns an in-process JSON snapshot:

- `http_request_total`
- `http_request_duration_ms`
- `database_readiness_check_total`
- `database_readiness_duration_ms`
- `retrieval_query_total`
- `retrieval_duration_ms`
- `retrieval_candidate_total`
- `retrieval_empty_result_total`
- `indexing_operation_total`
- `indexing_duration_ms`
- `indexing_chunk_total`
- `indexing_embedding_total`
- `provider_operation_total`
- `provider_operation_duration_ms`

Labels are deliberately low cardinality. They may include route templates,
HTTP method, status category, success flag, retrieval stage, provider name,
model name, and operation type. They must not include request IDs, user IDs,
document IDs, filenames, questions, answer text, prompt text, or raw evidence.

When authentication is enabled, `/metrics` requires the same bearer-token
authentication boundary as other protected operational routes. In production,
expose this endpoint only to trusted operators or behind private networking.

## Retrieval Metrics

The production query engine records retrieval duration and candidate counts for:

- vector retrieval
- BM25 retrieval
- fused results
- final reranked results
- empty-evidence outcomes

These metrics describe pipeline shape and health. They do not expose ranking
scores, source text, document identity, or user queries.

## Indexing Metrics

Document indexing records operation success/failure, total duration, chunk count,
and embedding count. Counts are aggregate-only and do not expose filenames,
document identifiers, chunk identifiers, upload bytes, or extracted text.

## Provider Metrics

Provider observation adapters are available for embedding and generation
providers. They record operation count, latency, success/failure, provider name,
and configured model name only. Token usage is not emitted unless a provider
returns reliable usage data through a safe contract.

## Current Limitations

LoreForge does not yet ship Prometheus, OpenTelemetry, external collectors,
dashboards, alerting rules, or long-term metrics persistence. The in-process
snapshot resets when the application restarts.
