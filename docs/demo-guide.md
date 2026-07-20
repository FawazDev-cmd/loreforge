# Demo Guide

This guide gives time-boxed ways to demonstrate LoreForge without relying on
private data or paid infrastructure.

## 5-Minute Demo

Goal: show that LoreForge is a production-minded backend, not a notebook.

1. Open README and describe the architecture briefly.
2. Run:

   ```powershell
   uv run --locked pytest tests/test_health.py tests/evaluation/test_day39_runner_cli.py
   ```

3. Start the API:

   ```powershell
   uv run --locked uvicorn loreforge.main:app --app-dir src
   ```

4. Visit:

   - `GET /health`
   - `GET /ready`
   - `GET /metrics`

5. Explain that default `/ask` is honestly degraded until providers and evidence
   are configured.

## 15-Minute Demo

Goal: show the vertical slice and quality controls.

1. Show repository structure and `ApplicationContainer`.
2. Show document processing modules under `src/loreforge/documents`.
3. Show retrieval modules: BM25, vector index, hybrid RRF, reranking.
4. Show query composition in `src/loreforge/query/engine.py`.
5. Run the golden evaluation gate:

   ```powershell
   uv run --locked python -m loreforge.evaluation --dataset tests/fixtures/evaluation/golden_dataset.json --thresholds tests/fixtures/evaluation/thresholds.json --output .tmp/evaluation-golden-report.json --human
   ```

6. Run the degraded gate and point out exit code `1`:

   ```powershell
   uv run --locked python -m loreforge.evaluation --dataset tests/fixtures/evaluation/degraded_dataset.json --thresholds tests/fixtures/evaluation/thresholds.json --output .tmp/evaluation-degraded-report.json --human
   ```

7. Show `docs/observability.md` and `/metrics`.

## 30-Minute Demo

Goal: walk through backend engineering depth.

1. Start with the problem statement and local-first constraints.
2. Walk through ingestion lifecycle:
   - upload validation
   - parsing
   - normalization
   - chunking
   - embedding/indexing
   - catalog/indexing state transitions
3. Walk through retrieval/generation:
   - query embedding
   - vector retrieval
   - BM25 retrieval
   - RRF
   - reranking
   - evidence context
   - grounded prompt
   - provider generation
   - citation enforcement
4. Walk through production hardening:
   - typed settings
   - PostgreSQL migrations
   - authentication and ownership
   - readiness and request IDs
   - metrics
5. Walk through quality:
   - pytest
   - Ruff
   - mypy
   - deterministic evaluation gate
6. Close with limitations and roadmap.

## Suggested Talking Points

- The default runtime is safe and zero-cost.
- Live providers are behind typed provider contracts.
- Core logic is not tied to FastAPI.
- Reports and logs avoid sensitive content.
- The project intentionally distinguishes implemented capabilities from planned
  future work.
