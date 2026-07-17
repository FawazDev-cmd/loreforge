"""Deterministic grounded-answer evaluation helpers."""

from re import compile, fullmatch

from loreforge.evaluation.models import AnswerMetrics, EvaluationCase
from loreforge.generation import ValidatedGroundedAnswer

_CITATION_MARKER_PATTERN = compile(r"(?<!\[)\[S[1-9][0-9]*\](?!\])")
_CITATION_ID_PATTERN = r"S[1-9][0-9]*"


def normalize_answer_text(text: str) -> str:
    """Normalize answer text for deterministic exact-match evaluation."""
    if not text.strip():
        msg = "text must not be empty"
        raise ValueError(msg)

    without_citations = _CITATION_MARKER_PATTERN.sub("", text)
    collapsed = " ".join(without_citations.casefold().split())
    return collapsed.strip()


def evaluate_citations(
    *,
    expected_citation_ids: tuple[str, ...],
    observed_citation_ids: tuple[str, ...],
) -> tuple[float, float]:
    """Evaluate citation precision and recall using citation ID sets."""
    _validate_citation_ids(expected_citation_ids, "expected_citation_ids")
    _validate_citation_ids(observed_citation_ids, "observed_citation_ids")

    expected = set(expected_citation_ids)
    observed = set(observed_citation_ids)
    overlap = expected & observed

    if observed:
        precision = len(overlap) / len(observed)
    else:
        precision = 1.0 if not expected else 0.0

    recall = len(overlap) / len(expected) if expected else 1.0
    return float(precision), float(recall)


def evaluate_answer(
    *,
    case: EvaluationCase,
    answer: ValidatedGroundedAnswer,
) -> AnswerMetrics:
    """Evaluate citation use and optional normalized exact match for an answer."""
    citation_precision, citation_recall = evaluate_citations(
        expected_citation_ids=case.expected_citation_ids,
        observed_citation_ids=answer.citation_validation.citation_ids,
    )

    if case.expected_answer is None:
        normalized_exact_match = None
    else:
        expected = normalize_answer_text(case.expected_answer)
        observed = normalize_answer_text(answer.grounded_answer.answer_text)
        normalized_exact_match = 1.0 if expected == observed else 0.0

    return AnswerMetrics(
        citation_precision=float(citation_precision),
        citation_recall=float(citation_recall),
        normalized_exact_match=normalized_exact_match,
    )


def _validate_citation_ids(values: tuple[str, ...], name: str) -> None:
    for value in values:
        if fullmatch(_CITATION_ID_PATTERN, value) is None:
            msg = f"{name} values must match S followed by a positive integer"
            raise ValueError(msg)

    if len(set(values)) != len(values):
        msg = f"{name} must contain unique values"
        raise ValueError(msg)
