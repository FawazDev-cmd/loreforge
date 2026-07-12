# LoreForge

LoreForge is an early-stage Python project focused on establishing a small, tested API foundation for future document intelligence work. The current scope is intentionally limited to a minimal FastAPI application and basic project tooling.

## Local setup

1. Install `uv` if it is not already available.
2. Create the project environment and install all dependencies:

   ```bash
   uv sync --all-groups
   ```

## Run the API

```bash
uv run uvicorn loreforge.main:app --app-dir src
```

## Run tests

```bash
uv run pytest
```

## Lint and type-check

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```
