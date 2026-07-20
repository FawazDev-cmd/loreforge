# Configuration Reference

LoreForge configuration is centralized in `src/loreforge/settings.py` and loaded
through `load_settings()`. New runtime settings should be added there and to
`.env.example`; avoid scattered `os.getenv()` calls.

## Application

- `LOREFORGE_ENVIRONMENT`: `development`, `testing`, or `production`.
- `LOREFORGE_SERVICE_NAME`: service name returned by health endpoints.
- `LOREFORGE_API_TITLE`: FastAPI title.
- `LOREFORGE_API_VERSION`: API version.
- `LOREFORGE_PUBLIC_BASE_URL`: required in production.

Production rejects debug logging and fails fast when required public runtime
settings are missing.

## API

- `LOREFORGE_API_HOST`
- `LOREFORGE_API_PORT`
- `LOREFORGE_CORS_ALLOWED_ORIGINS`

CORS is documented for future production use. Do not open broad origins in
production without a specific frontend/deployment need.

## Logging

- `LOREFORGE_LOG_LEVEL`: `debug`, `info`, `warning`, or `error`.
- `LOREFORGE_STRUCTURED_LOGGING`
- `LOREFORGE_REQUEST_LOGGING_ENABLED`

Logs must not include secrets, auth headers, database URLs, prompts, full
questions, answers, raw document text, vectors, uploads, filenames, or provider
payloads.

## Providers

Provider selectors:

- `LOREFORGE_DOCUMENT_EMBEDDINGS_PROVIDER`
- `LOREFORGE_QUERY_EMBEDDINGS_PROVIDER`
- `LOREFORGE_RERANKER_PROVIDER`
- `LOREFORGE_LLM_PROVIDER`

Valid selections are controlled by typed settings. Providers are disabled by
default.

Gemini:

- `LOREFORGE_GEMINI_API_KEY`
- `LOREFORGE_GEMINI_GENERATION_MODEL`
- `LOREFORGE_GEMINI_EMBEDDING_MODEL`
- `LOREFORGE_GEMINI_TIMEOUT_SECONDS`
- `LOREFORGE_RUN_LIVE_GEMINI_SMOKE`

OpenRouter:

- `LOREFORGE_OPENROUTER_API_KEY`
- `LOREFORGE_OPENROUTER_MODEL`
- `LOREFORGE_OPENROUTER_BASE_URL`
- `LOREFORGE_OPENROUTER_TIMEOUT_SECONDS`

Local providers:

- `LOREFORGE_LOCAL_EMBEDDING_MODEL`
- `LOREFORGE_LOCAL_RERANKER_MODEL`
- `LOREFORGE_LOCAL_BATCH_SIZE`

Local models load only when explicitly configured.

## PostgreSQL

- `LOREFORGE_DATABASE_URL`
- `LOREFORGE_DATABASE_POOL_MIN_SIZE`
- `LOREFORGE_DATABASE_POOL_MAX_SIZE`
- `LOREFORGE_DATABASE_MIGRATIONS_ENABLED`
- `LOREFORGE_DATABASE_MIGRATIONS_PATH`
- `LOREFORGE_RUN_LIVE_DATABASE_SMOKE`

Leave `LOREFORGE_DATABASE_URL` empty for zero-cost in-memory startup. Run Alembic
migrations before using a fresh database.

## Storage

- `LOREFORGE_STORAGE_PROVIDER`
- `LOREFORGE_STORAGE_LOCAL_PATH`
- `LOREFORGE_SUPABASE_URL`
- `LOREFORGE_SUPABASE_STORAGE_BUCKET`
- `LOREFORGE_SUPABASE_SERVICE_ROLE_KEY`

Durable uploaded-file storage is not implemented yet. These settings preserve a
typed upgrade path and should not be treated as a current storage feature.

## Authentication

- `LOREFORGE_AUTH_PROVIDER`
- `LOREFORGE_AUTH_API_KEYS`
- `LOREFORGE_AUTH_JWT_ISSUER`
- `LOREFORGE_AUTH_JWT_AUDIENCE`
- `LOREFORGE_AUTH_JWKS_URL`

API-key bearer authentication is implemented. JWT settings are placeholders for a
future provider and are not active by default.

`LOREFORGE_AUTH_API_KEYS` uses comma-separated
`user_uuid:api_key[:display_name]` entries. Never commit real keys.

## Observability

- `LOREFORGE_METRICS_ENABLED`
- `LOREFORGE_RECORD_QUERY_OBSERVATIONS`

Metrics are in-process and provider-neutral. They reset on process restart.
