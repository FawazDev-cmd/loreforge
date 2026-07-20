"""Deterministic offline evaluation runner."""

from collections import defaultdict
from collections.abc import Sequence
from statistics import mean
from time import perf_counter
from uuid import UUID

from loreforge.evaluation.dataset import EvaluationDataset, EvaluationDatasetCase
from loreforge.evaluation.gate import (
    EvaluationThresholds,
    evaluate_gate,
    thresholds_as_dict,
)
from loreforge.evaluation.quality import (
    evaluate_citation_quality,
    evaluate_groundedness,
    evaluate_retrieval_quality,
)
from loreforge.evaluation.reporting import EvaluationRunReport


def run_fixture_evaluation(
    *,
    dataset: EvaluationDataset,
    thresholds: EvaluationThresholds,
    k_values: Sequence[int] = (3,),
) -> EvaluationRunReport:
    """Evaluate deterministic fixture observations and apply thresholds."""
    if not k_values:
        msg = "k_values must contain at least one K"
        raise ValueError(msg)
    k = _first_k(k_values)
    case_reports: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    for case in sorted(dataset.cases, key=lambda item: item.case_id):
        started = perf_counter()
        try:
            case_reports.append(_evaluate_case(case, k, started))
        except Exception:
            errors.append({"case_id": case.case_id, "category": "evaluator_error"})
    aggregates = _aggregate(case_reports, errors)
    gate = evaluate_gate(aggregates=aggregates, thresholds=thresholds)
    tag_summaries = _tag_summaries(dataset, case_reports)
    return EvaluationRunReport(
        dataset_name=dataset.name,
        schema_version=dataset.schema_version,
        passed=gate.passed and not errors,
        aggregates=aggregates,
        thresholds=thresholds_as_dict(thresholds),
        failed_thresholds=gate.failed_thresholds,
        cases=tuple(case_reports),
        tag_summaries=tag_summaries,
        errors=tuple(errors),
    )


def _evaluate_case(
    case: EvaluationDatasetCase,
    k: int,
    started: float,
) -> dict[str, object]:
    retrieval = evaluate_retrieval_quality(
        case=case,
        retrieved_chunk_ids=case.observed_retrieved_chunk_ids,
        retrieved_source_document_ids=case.observed_retrieved_source_document_ids,
        k=k,
    )
    evidence_citation_ids = tuple(
        f"S{index}" for index, _ in enumerate(case.observed_evidence_chunk_ids, start=1)
    )
    cited_source_document_ids = _cited_sources(
        observed_citation_ids=case.observed_citation_ids,
        evidence_chunk_ids=case.observed_evidence_chunk_ids,
        evidence_source_document_ids=case.observed_retrieved_source_document_ids,
    )
    citations = evaluate_citation_quality(
        expected_citation_ids=case.expected_citation_ids,
        observed_citation_ids=case.observed_citation_ids,
        evidence_citation_ids=evidence_citation_ids,
        expected_source_document_ids=case.expected_source_document_ids,
        cited_source_document_ids=cited_source_document_ids,
    )
    groundedness = evaluate_groundedness(
        case=case,
        answer_text=case.observed_answer_text,
        evidence_chunk_ids=case.observed_evidence_chunk_ids,
    )
    failure_reasons = _failure_reasons(
        case=case,
        retrieval_hit=retrieval.hit_rate,
        retrieval_recall=retrieval.recall,
        citation_recall=citations.citation_recall,
        citation_validity=citations.citation_validity,
        required_fact_coverage=groundedness.required_fact_coverage,
        forbidden_claim_score=groundedness.forbidden_claim_score,
        abstention_correctness=groundedness.abstention_correctness,
    )
    return {
        "case_id": case.case_id,
        "tags": list(case.tags),
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
        "latency_ms": float((perf_counter() - started) * 1000.0),
        "retrieval": {
            "k": retrieval.k,
            "hit_rate": retrieval.hit_rate,
            "precision": retrieval.precision,
            "recall": retrieval.recall,
            "reciprocal_rank": retrieval.reciprocal_rank,
            "ndcg": retrieval.ndcg,
            "source_document_recall": retrieval.source_document_recall,
            "empty_result_correctness": retrieval.empty_result_correctness,
        },
        "citation": {
            "presence": citations.citation_presence,
            "validity": citations.citation_validity,
            "precision": citations.citation_precision,
            "recall": citations.citation_recall,
            "evidence_consistency": citations.evidence_consistency,
            "unsupported_count": citations.unsupported_citation_count,
            "duplicate_count": citations.duplicate_citation_count,
            "malformed_count": citations.malformed_citation_count,
            "source_coverage": citations.source_coverage,
        },
        "groundedness": {
            "required_fact_coverage": groundedness.required_fact_coverage,
            "forbidden_claim_score": groundedness.forbidden_claim_score,
            "abstention_correctness": groundedness.abstention_correctness,
            "evidence_coverage": groundedness.evidence_coverage,
        },
    }


def _aggregate(
    cases: list[dict[str, object]],
    errors: list[dict[str, str]],
) -> dict[str, float]:
    return {
        "case_count": float(len(cases)),
        "error_count": float(len(errors)),
        "mean_hit_rate_at_k": _mean(_values(cases, "retrieval", "hit_rate")),
        "mean_recall_at_k": _mean(_values(cases, "retrieval", "recall")),
        "mean_mrr": _mean(_values(cases, "retrieval", "reciprocal_rank")),
        "mean_ndcg_at_k": _mean(_non_null_values(cases, "retrieval", "ndcg")),
        "mean_citation_validity": _mean(_values(cases, "citation", "validity")),
        "mean_citation_coverage": _mean(_values(cases, "citation", "recall")),
        "mean_required_fact_coverage": _mean(
            _values(cases, "groundedness", "required_fact_coverage")
        ),
        "mean_abstention_correctness": _mean(
            _non_null_values(cases, "groundedness", "abstention_correctness")
        ),
    }


def _tag_summaries(
    dataset: EvaluationDataset,
    case_reports: list[dict[str, object]],
) -> dict[str, dict[str, float]]:
    by_id = {case["case_id"]: case for case in case_reports}
    tags: dict[str, list[dict[str, object]]] = defaultdict(list)
    for case in dataset.cases:
        report = by_id.get(case.case_id)
        if report is None:
            continue
        for tag in case.tags:
            tags[tag].append(report)
    return {
        tag: {
            "case_count": float(len(items)),
            "mean_hit_rate_at_k": _mean(_values(items, "retrieval", "hit_rate")),
            "mean_citation_coverage": _mean(_values(items, "citation", "recall")),
        }
        for tag, items in sorted(tags.items())
    }


def _failure_reasons(
    *,
    case: EvaluationDatasetCase,
    retrieval_hit: float,
    retrieval_recall: float,
    citation_recall: float,
    citation_validity: float,
    required_fact_coverage: float,
    forbidden_claim_score: float,
    abstention_correctness: float | None,
) -> list[str]:
    reasons: list[str] = []
    if case.expect_no_evidence:
        if retrieval_hit != 1.0:
            reasons.append("expected_empty_retrieval")
    elif retrieval_hit < 1.0 or retrieval_recall < 1.0:
        reasons.append("retrieval")
    if citation_recall < 1.0 or citation_validity < 1.0:
        reasons.append("citation")
    if required_fact_coverage < 1.0 or forbidden_claim_score < 1.0:
        reasons.append("groundedness")
    if abstention_correctness is not None and abstention_correctness < 1.0:
        reasons.append("abstention")
    return reasons


def _cited_sources(
    *,
    observed_citation_ids: tuple[str, ...],
    evidence_chunk_ids: tuple[UUID, ...],
    evidence_source_document_ids: tuple[UUID, ...],
) -> tuple[UUID, ...]:
    source_by_citation = {
        f"S{index}": document_id
        for index, document_id in enumerate(evidence_source_document_ids, start=1)
        if index <= len(evidence_chunk_ids)
    }
    return tuple(
        source_by_citation[citation_id]
        for citation_id in observed_citation_ids
        if citation_id in source_by_citation
    )


def _values(
    cases: list[dict[str, object]],
    section: str,
    key: str,
) -> tuple[float, ...]:
    return tuple(float(case[section][key]) for case in cases)  # type: ignore[index]


def _non_null_values(
    cases: list[dict[str, object]],
    section: str,
    key: str,
) -> tuple[float, ...]:
    values = []
    for case in cases:
        value = case[section][key]  # type: ignore[index]
        if value is not None:
            values.append(float(value))
    return tuple(values)


def _mean(values: tuple[float, ...]) -> float:
    if not values:
        return 1.0
    return float(mean(values))


def _first_k(k_values: Sequence[int]) -> int:
    first = k_values[0]
    first_object: object = first
    if type(first_object) is not int or first <= 0:
        msg = "k_values must contain positive integers"
        raise ValueError(msg)
    return first
