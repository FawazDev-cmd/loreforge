"""Evaluation suite orchestration and report aggregation."""

from uuid import UUID

from loreforge.evaluation.answers import evaluate_answer
from loreforge.evaluation.models import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationReport,
)
from loreforge.evaluation.retrieval import evaluate_retrieval
from loreforge.generation import ValidatedGroundedAnswer


def evaluate_case(
    *,
    case: EvaluationCase,
    retrieved_chunk_ids: tuple[UUID, ...],
    answer: ValidatedGroundedAnswer,
    k: int,
) -> EvaluationCaseResult:
    """Evaluate retrieval and answer metrics for one case."""
    if answer.grounded_answer.question != case.question:
        msg = "answer question must match evaluation case question"
        raise ValueError(msg)

    retrieval = evaluate_retrieval(
        relevant_chunk_ids=case.relevant_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        k=k,
    )
    answer_metrics = evaluate_answer(case=case, answer=answer)
    return EvaluationCaseResult(
        case_id=case.case_id,
        retrieval=retrieval,
        answer=answer_metrics,
    )


def build_evaluation_report(
    results: tuple[EvaluationCaseResult, ...],
) -> EvaluationReport:
    """Build an aggregate evaluation report from case results."""
    if not results:
        msg = "results must contain at least one result"
        raise ValueError(msg)

    case_ids = tuple(result.case_id for result in results)
    if len(set(case_ids)) != len(case_ids):
        msg = "case IDs must be unique"
        raise ValueError(msg)

    exact_values = tuple(
        result.answer.normalized_exact_match
        for result in results
        if result.answer.normalized_exact_match is not None
    )
    mean_exact = _mean(exact_values) if exact_values else None

    return EvaluationReport(
        results=results,
        mean_hit_rate=_mean(tuple(result.retrieval.hit_rate for result in results)),
        mean_precision=_mean(tuple(result.retrieval.precision for result in results)),
        mean_recall=_mean(tuple(result.retrieval.recall for result in results)),
        mean_reciprocal_rank=_mean(
            tuple(result.retrieval.reciprocal_rank for result in results)
        ),
        mean_citation_precision=_mean(
            tuple(result.answer.citation_precision for result in results)
        ),
        mean_citation_recall=_mean(
            tuple(result.answer.citation_recall for result in results)
        ),
        mean_normalized_exact_match=mean_exact,
    )


def _mean(values: tuple[float, ...]) -> float:
    return float(sum(values) / len(values))
