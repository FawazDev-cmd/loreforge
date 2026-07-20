# Evaluation Framework and Quality Regression

LoreForge uses deterministic offline evaluation as the first production baseline
for RAG quality. The evaluator measures retrieval quality, citation correctness,
groundedness, and abstention behavior without calling live providers, external
services, PostgreSQL, Docker, or the FastAPI server.

## Why Evaluation Matters

RAG systems can regress without obvious unit-test failures. Ranking changes,
indexing bugs, prompt changes, provider behavior, or citation enforcement issues
can reduce answer quality while the API still returns `200`. The deterministic
gate provides a repeatable CI-ready signal before release.

## Dataset Format

Datasets are JSON files with schema version `1.0`.

Top-level fields:

- `name`
- `schema_version`
- `description`
- optional `metadata`
- `cases`

Each case may include:

- `case_id`
- `question`
- `tags`
- `expected_chunk_ids`
- `expected_source_document_ids`
- `expected_citation_ids`
- `relevance_grades`
- `required_facts`
- `forbidden_claims`
- `expect_no_evidence`
- `expect_abstention`
- deterministic fixture observations such as `observed_retrieved_chunk_ids`,
  `observed_evidence_chunk_ids`, `observed_citation_ids`, and
  `observed_answer_text`

Committed fixtures must use synthetic or public-safe content. Do not include
secrets, credentials, private customer text, production questions, raw document
content, or provider payloads.

## Golden Fixture

The current golden fixture is `tests/fixtures/evaluation/golden_dataset.json`.
It covers:

- exact lexical retrieval
- semantic retrieval
- hybrid retrieval value
- metadata filtering
- ownership isolation
- multi-source evidence
- insufficient-evidence abstention
- citation-relevant answers
- a near-match/distractor case

`tests/fixtures/evaluation/degraded_dataset.json` intentionally fails the gate
and proves that regression exit behavior works.

## Metrics

Retrieval metrics:

- hit rate at K
- precision at K
- recall at K
- reciprocal rank / MRR
- NDCG at K when relevance grades are present
- source-document recall
- empty-result correctness for no-evidence cases

Citation metrics:

- citation presence
- citation validity
- citation precision
- citation recall / coverage
- citation-to-evidence consistency
- unsupported, duplicate, and malformed citation counts
- source-level coverage

Groundedness checks:

- required fact coverage
- forbidden claim detection
- abstention correctness
- evidence coverage

The groundedness checks are deterministic phrase checks over explicitly authored
facts. They are not a semantic truth judge and do not replace human review or a
future optional model judge.

## Thresholds

Thresholds live in `tests/fixtures/evaluation/thresholds.json`.

Supported gates:

- `min_hit_rate_at_k`
- `min_recall_at_k`
- `min_mrr`
- `min_ndcg_at_k`
- `min_citation_validity`
- `min_citation_coverage`
- `min_required_fact_coverage`
- `min_abstention_correctness`
- `max_error_count`

Thresholds are version controlled and must not be silently lowered to make a
regression pass.

## Local Commands

Passing golden fixture:

```powershell
uv run --locked python -m loreforge.evaluation --dataset tests/fixtures/evaluation/golden_dataset.json --thresholds tests/fixtures/evaluation/thresholds.json --output .tmp/evaluation-golden-report.json --human
```

Intentional degraded fixture:

```powershell
uv run --locked python -m loreforge.evaluation --dataset tests/fixtures/evaluation/degraded_dataset.json --thresholds tests/fixtures/evaluation/thresholds.json --output .tmp/evaluation-degraded-report.json --human
```

Exit codes:

- `0`: passed
- `1`: quality regression
- `2`: configuration or evaluator setup error

## CI Readiness

A future CI workflow can run the golden fixture after tests, Ruff, and mypy, then
retain the JSON report as an artifact. The evaluator is offline and deterministic
by default.

## Report Privacy

Machine-readable reports include case IDs, aggregate metrics, thresholds, failed
threshold names, and failure categories. Reports intentionally omit raw questions,
full answers, document text, credentials, database URLs, provider payloads, and
secret-like values.

## Adding a Case

1. Add a synthetic or public-safe case to the JSON fixture.
2. Use stable IDs for chunks, sources, and citations.
3. Add relevance grades only when the ordering expectation is intentional.
4. Add `required_facts` for deterministic fact checks.
5. Add `forbidden_claims` for known unsafe or unsupported claims.
6. Run the golden and degraded evaluation commands.
7. Update thresholds only when the change is intentional and explainable.

## Current Limitations

- No live LLM judge is configured.
- No semantic fact verification is attempted.
- The fixture mode evaluates deterministic observations, not a live production
  database or provider stack.
- Reports are generated locally and are not persisted beyond the requested output
  file.
