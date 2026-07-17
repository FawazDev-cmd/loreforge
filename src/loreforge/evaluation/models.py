"""Immutable evaluation model contracts."""

from dataclasses import dataclass
from math import isfinite
from re import fullmatch
from uuid import UUID

_CITATION_ID_PATTERN = r"S[1-9][0-9]*"


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """Expected retrieval and answer targets for one evaluation case."""

    case_id: str
    question: str
    relevant_chunk_ids: tuple[UUID, ...]
    expected_citation_ids: tuple[str, ...]
    expected_answer: str | None = None

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            msg = "case_id must not be empty"
            raise ValueError(msg)

        if not self.question.strip():
            msg = "question must not be empty"
            raise ValueError(msg)

        if not self.relevant_chunk_ids:
            msg = "relevant_chunk_ids must contain at least one ID"
            raise ValueError(msg)

        if len(set(self.relevant_chunk_ids)) != len(self.relevant_chunk_ids):
            msg = "relevant_chunk_ids must be unique"
            raise ValueError(msg)

        _validate_citation_id_tuple(self.expected_citation_ids, "expected_citation_ids")

        if self.expected_answer is not None and not self.expected_answer.strip():
            msg = "expected_answer must not be empty when provided"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    """Ranked retrieval metrics at a configured K."""

    k: int
    hit_rate: float
    precision: float
    recall: float
    reciprocal_rank: float

    def __post_init__(self) -> None:
        _validate_positive_int(self.k, "k")
        _validate_metric(self.hit_rate, "hit_rate")
        _validate_metric(self.precision, "precision")
        _validate_metric(self.recall, "recall")
        _validate_metric(self.reciprocal_rank, "reciprocal_rank")


@dataclass(frozen=True, slots=True)
class AnswerMetrics:
    """Citation and normalized exact-match metrics for an answer."""

    citation_precision: float
    citation_recall: float
    normalized_exact_match: float | None

    def __post_init__(self) -> None:
        _validate_metric(self.citation_precision, "citation_precision")
        _validate_metric(self.citation_recall, "citation_recall")
        if self.normalized_exact_match is not None:
            _validate_metric(self.normalized_exact_match, "normalized_exact_match")


@dataclass(frozen=True, slots=True)
class EvaluationCaseResult:
    """Evaluation metrics for one case."""

    case_id: str
    retrieval: RetrievalMetrics
    answer: AnswerMetrics

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            msg = "case_id must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Aggregate evaluation metrics across multiple cases."""

    results: tuple[EvaluationCaseResult, ...]
    mean_hit_rate: float
    mean_precision: float
    mean_recall: float
    mean_reciprocal_rank: float
    mean_citation_precision: float
    mean_citation_recall: float
    mean_normalized_exact_match: float | None

    def __post_init__(self) -> None:
        if not self.results:
            msg = "results must contain at least one result"
            raise ValueError(msg)

        case_ids = tuple(result.case_id for result in self.results)
        if len(set(case_ids)) != len(case_ids):
            msg = "case IDs must be unique"
            raise ValueError(msg)

        _validate_metric(self.mean_hit_rate, "mean_hit_rate")
        _validate_metric(self.mean_precision, "mean_precision")
        _validate_metric(self.mean_recall, "mean_recall")
        _validate_metric(self.mean_reciprocal_rank, "mean_reciprocal_rank")
        _validate_metric(self.mean_citation_precision, "mean_citation_precision")
        _validate_metric(self.mean_citation_recall, "mean_citation_recall")
        if self.mean_normalized_exact_match is not None:
            _validate_metric(
                self.mean_normalized_exact_match,
                "mean_normalized_exact_match",
            )


def _validate_positive_int(value: int, name: str) -> None:
    value_object: object = value
    if type(value_object) is not int:
        msg = f"{name} must be an integer"
        raise ValueError(msg)

    if value <= 0:
        msg = f"{name} must be greater than zero"
        raise ValueError(msg)


def _validate_metric(value: float, name: str) -> None:
    value_object: object = value
    if type(value_object) is not float:
        msg = f"{name} must be a float"
        raise ValueError(msg)

    if not isfinite(value):
        msg = f"{name} must be finite"
        raise ValueError(msg)

    if not 0.0 <= value <= 1.0:
        msg = f"{name} must be between 0.0 and 1.0"
        raise ValueError(msg)


def _validate_citation_id_tuple(values: tuple[str, ...], name: str) -> None:
    for value in values:
        if fullmatch(_CITATION_ID_PATTERN, value) is None:
            msg = f"{name} values must match S followed by a positive integer"
            raise ValueError(msg)

    if len(set(values)) != len(values):
        msg = f"{name} must contain unique values"
        raise ValueError(msg)
