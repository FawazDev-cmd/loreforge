"""Deterministic retrieval, citation, and groundedness metrics."""

from dataclasses import dataclass
from math import isfinite, log2
from re import compile, fullmatch
from uuid import UUID

from loreforge.evaluation.dataset import EvaluationDatasetCase

_CITATION_ID_PATTERN = r"S[1-9][0-9]*"
_WORD_PATTERN = compile(r"[a-z0-9]+")
_ABSTENTION_PHRASES = (
    "not enough evidence",
    "insufficient evidence",
    "cannot answer",
    "do not have enough",
)


@dataclass(frozen=True, slots=True)
class RetrievalQualityMetrics:
    """Retrieval quality for one case at one K."""

    k: int
    hit_rate: float
    precision: float
    recall: float
    reciprocal_rank: float
    ndcg: float | None
    source_document_recall: float | None
    empty_result_correctness: float | None


@dataclass(frozen=True, slots=True)
class CitationQualityMetrics:
    """Citation quality for one structured answer."""

    citation_presence: float
    citation_validity: float
    citation_precision: float
    citation_recall: float
    evidence_consistency: float
    unsupported_citation_count: int
    duplicate_citation_count: int
    malformed_citation_count: int
    source_coverage: float | None


@dataclass(frozen=True, slots=True)
class GroundednessMetrics:
    """Deterministic fact, forbidden-claim, and abstention checks."""

    required_fact_coverage: float
    forbidden_claim_score: float
    abstention_correctness: float | None
    evidence_coverage: float


def evaluate_retrieval_quality(
    *,
    case: EvaluationDatasetCase,
    retrieved_chunk_ids: tuple[UUID, ...],
    retrieved_source_document_ids: tuple[UUID, ...],
    k: int,
) -> RetrievalQualityMetrics:
    """Evaluate ranked retrieval with binary and optional graded relevance."""
    _validate_k(k)
    considered = _dedupe(retrieved_chunk_ids)[:k]
    relevant = set(case.expected_chunk_ids)
    matches = tuple(chunk_id for chunk_id in considered if chunk_id in relevant)
    if case.expect_no_evidence:
        empty_correct = 1.0 if not retrieved_chunk_ids else 0.0
    else:
        empty_correct = None
    precision = len(matches) / len(considered) if considered else 0.0
    recall = (
        len(matches) / len(relevant)
        if relevant
        else (1.0 if case.expect_no_evidence else 0.0)
    )
    ndcg = (
        _ndcg(considered, case.relevance_grades, k) if case.relevance_grades else None
    )
    source_recall = _source_recall(case, retrieved_source_document_ids, k)
    reciprocal_rank = (
        1.0
        if case.expect_no_evidence and not retrieved_chunk_ids
        else _reciprocal_rank(_dedupe(retrieved_chunk_ids), relevant)
    )
    return RetrievalQualityMetrics(
        k=k,
        hit_rate=1.0
        if matches
        else (1.0 if case.expect_no_evidence and not considered else 0.0),
        precision=float(precision),
        recall=float(recall),
        reciprocal_rank=reciprocal_rank,
        ndcg=ndcg,
        source_document_recall=source_recall,
        empty_result_correctness=empty_correct,
    )


def evaluate_citation_quality(
    *,
    expected_citation_ids: tuple[str, ...],
    observed_citation_ids: tuple[str, ...],
    evidence_citation_ids: tuple[str, ...],
    expected_source_document_ids: tuple[UUID, ...],
    cited_source_document_ids: tuple[UUID, ...],
) -> CitationQualityMetrics:
    """Evaluate structured citation identifiers without brittle answer matching."""
    malformed = tuple(
        citation_id
        for citation_id in observed_citation_ids
        if fullmatch(_CITATION_ID_PATTERN, citation_id) is None
    )
    valid_observed = tuple(
        citation_id
        for citation_id in observed_citation_ids
        if fullmatch(_CITATION_ID_PATTERN, citation_id) is not None
    )
    duplicate_count = len(valid_observed) - len(set(valid_observed))
    expected = set(expected_citation_ids)
    observed = set(valid_observed)
    evidence = set(evidence_citation_ids)
    unsupported = observed - evidence
    overlap = observed & expected
    precision = (
        len(overlap) / len(observed) if observed else (1.0 if not expected else 0.0)
    )
    recall = (
        len(overlap) / len(expected) if expected else (1.0 if not observed else 0.0)
    )
    evidence_consistency = 1.0 if not unsupported and not malformed else 0.0
    if expected_source_document_ids:
        source_coverage = len(
            set(cited_source_document_ids) & set(expected_source_document_ids)
        ) / len(set(expected_source_document_ids))
    else:
        source_coverage = None
    return CitationQualityMetrics(
        citation_presence=1.0 if observed else (1.0 if not expected else 0.0),
        citation_validity=1.0 if not malformed and duplicate_count == 0 else 0.0,
        citation_precision=float(precision),
        citation_recall=float(recall),
        evidence_consistency=evidence_consistency,
        unsupported_citation_count=len(unsupported),
        duplicate_citation_count=duplicate_count,
        malformed_citation_count=len(malformed),
        source_coverage=None if source_coverage is None else float(source_coverage),
    )


def evaluate_groundedness(
    *,
    case: EvaluationDatasetCase,
    answer_text: str | None,
    evidence_chunk_ids: tuple[UUID, ...],
) -> GroundednessMetrics:
    """Evaluate deterministic authored facts, forbidden claims, and abstention."""
    normalized = _normalize(answer_text or "")
    if case.required_facts:
        required_hits = sum(
            1 for fact in case.required_facts if _normalize(fact) in normalized
        )
        fact_coverage = required_hits / len(case.required_facts)
    else:
        fact_coverage = 1.0
    forbidden_hits = sum(
        1 for claim in case.forbidden_claims if _normalize(claim) in normalized
    )
    forbidden_score = 1.0 if forbidden_hits == 0 else 0.0
    if case.expect_abstention:
        abstention = 1.0 if _is_abstention(normalized) else 0.0
    elif answer_text is not None:
        abstention = 0.0 if _is_abstention(normalized) else 1.0
    else:
        abstention = None
    expected_evidence = set(case.expected_chunk_ids)
    if expected_evidence:
        evidence_coverage = len(set(evidence_chunk_ids) & expected_evidence) / len(
            expected_evidence
        )
    else:
        evidence_coverage = (
            1.0 if case.expect_no_evidence and not evidence_chunk_ids else 0.0
        )
    return GroundednessMetrics(
        required_fact_coverage=float(fact_coverage),
        forbidden_claim_score=float(forbidden_score),
        abstention_correctness=abstention,
        evidence_coverage=float(evidence_coverage),
    )


def _dedupe(values: tuple[UUID, ...]) -> tuple[UUID, ...]:
    seen: set[UUID] = set()
    result: list[UUID] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _reciprocal_rank(retrieved: tuple[UUID, ...], relevant: set[UUID]) -> float:
    for rank, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in relevant:
            return float(1.0 / rank)
    return 0.0


def _ndcg(retrieved: tuple[UUID, ...], grades: dict[UUID, int], k: int) -> float:
    ideal = tuple(sorted(grades.values(), reverse=True))[:k]
    ideal_dcg = _dcg(ideal)
    if ideal_dcg == 0.0:
        return 0.0
    observed = tuple(grades.get(chunk_id, 0) for chunk_id in retrieved[:k])
    return float(_dcg(observed) / ideal_dcg)


def _dcg(grades: tuple[int, ...]) -> float:
    return float(
        sum(((2**grade) - 1) / log2(index + 2) for index, grade in enumerate(grades))
    )


def _source_recall(
    case: EvaluationDatasetCase,
    retrieved_source_document_ids: tuple[UUID, ...],
    k: int,
) -> float | None:
    expected = set(case.expected_source_document_ids)
    if not expected:
        return None
    considered = set(_dedupe(retrieved_source_document_ids)[:k])
    return float(len(considered & expected) / len(expected))


def _normalize(text: str) -> str:
    return " ".join(_WORD_PATTERN.findall(text.casefold()))


def _is_abstention(normalized_text: str) -> bool:
    return any(phrase in normalized_text for phrase in _ABSTENTION_PHRASES)


def _validate_k(k: int) -> None:
    k_object: object = k
    if type(k_object) is not int or k <= 0:
        msg = "k must be a positive integer"
        raise ValueError(msg)


def _validate_metric(value: float) -> None:
    if not isfinite(value) or not 0.0 <= value <= 1.0:
        msg = "metric must be finite and between 0.0 and 1.0"
        raise ValueError(msg)
