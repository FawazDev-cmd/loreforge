# Deployment Packaging

LoreForge ships a production-oriented Docker image and a minimal Docker Compose
configuration for local deployment validation.

## Docker Image

The Dockerfile uses:

- Python 3.13 slim base images
- a pinned `uv` image for locked dependency installation
- `uv sync --locked --no-dev` for deterministic runtime dependencies
- a non-root `loreforge` user
- copied Alembic migration files for optional startup migrations
- a lightweight `/health` container health check

Build locally:

```bash
docker build .
```

Run the image:

```bash
docker run --rm -p 8000:8000 --env-file .env.docker loreforge:latest
```

Do not bake secrets into the image. Use environment variables or an env file
provided by the deployment environment.

## Docker Compose

Validate Compose configuration:

```bash
docker compose config
```

Start locally:

```bash
docker compose up --build
```

Compose loads `.env` when present and keeps it optional for configuration
validation. The service binds `0.0.0.0` inside the container and exposes host
port `${LOREFORGE_API_PORT:-8000}`.

## Runtime Environment

Required for production:

- `LOREFORGE_ENVIRONMENT=production`
- `LOREFORGE_PUBLIC_BASE_URL=https://...`

Required only when enabling PostgreSQL:

- `LOREFORGE_DATABASE_URL`
- `LOREFORGE_DATABASE_POOL_MIN_SIZE`
- `LOREFORGE_DATABASE_POOL_MAX_SIZE`
- `LOREFORGE_DATABASE_MIGRATIONS_ENABLED`
- `LOREFORGE_DATABASE_MIGRATIONS_PATH`

Required only when enabling API-key authentication:

- `LOREFORGE_AUTH_PROVIDER=api_key`
- `LOREFORGE_AUTH_API_KEYS`

Required only when enabling Gemini/OpenRouter providers:

- the matching provider selection variables
- the matching provider API key and model variables

Never log, commit, or bake secrets into images.

## Health And Readiness

- `GET /health` is a liveness endpoint. It confirms the FastAPI process is
  running and does not check external dependencies.
- `GET /ready` is a readiness endpoint. It confirms the application container is
  initialized and checks configured critical dependencies such as PostgreSQL
  using the existing database health query.

Readiness intentionally does not call LLM providers, embedding providers, or
remote model APIs.

## Operational Notes

- Startup fails fast through typed settings validation.
- Production mode rejects debug logging.
- Startup and shutdown lifecycle events are logged without secrets.
- Database resources are disposed on application shutdown.
- Live provider/model calls remain opt-in through explicit configuration.
