# syntax=docker/dockerfile:1

FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.17 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

RUN uv sync --locked --no-dev


FROM python:3.13-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOREFORGE_API_HOST=0.0.0.0 \
    LOREFORGE_API_PORT=8000

WORKDIR /app

RUN groupadd --system loreforge \
    && useradd --system --gid loreforge --home-dir /app --shell /usr/sbin/nologin loreforge

COPY --from=builder --chown=loreforge:loreforge /app/.venv /app/.venv
COPY --chown=loreforge:loreforge src ./src
COPY --chown=loreforge:loreforge alembic.ini ./alembic.ini
COPY --chown=loreforge:loreforge migrations ./migrations

USER loreforge

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=3).read()"

CMD ["uvicorn", "loreforge.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
