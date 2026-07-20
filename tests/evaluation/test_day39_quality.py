from uuid import UUID

import pytest

from loreforge.evaluation.dataset import EvaluationDatasetCase
from loreforge.evaluation.quality import (
    evaluate_citation_quality,
    evaluate_groundedness,
    evaluate_retrieval_quality,
)

ID1 = UUID("00000000-0000-0000-0000-000000000001")
ID2 = UUID("00000000-0000-0000-0000-000000000002")
ID3 = UUID("00000000-0000-0000-0000-000000000003")
DOC1 = UUID("00000000-0000-0000-0000-000000000101")
DOC2 = UUID("00000000-0000-0000-0000-000000000102")


def test_retrieval_quality_perfect_ranking() -> None:
    metrics = evaluate_retrieval_quality(
        case=_case(),
        retrieved_chunk_ids=(ID1, ID2),
        retrieved_source_document_ids=(DOC1, DOC2),
        k=2,
    )

    assert metrics.hit_rate == 1.0
    assert metrics.precision == 0.5
    assert metrics.recall == 1.0
    assert metrics.reciprocal_rank == 1.0
    assert metrics.source_document_recall == 1.0


def test_retrieval_quality_partial_and_duplicate_results() -> None:
    metrics = evaluate_retrieval_quality(
        case=_case(expected=(ID2,)),
        retrieved_chunk_ids=(ID1, ID1, ID2),
        retrieved_source_document_ids=(DOC2,),
        k=2,
    )

    assert metrics.hit_rate == 1.0
    assert metrics.reciprocal_rank == 0.5


def test_retrieval_quality_no_answer_case() -> None:
    metrics = evaluate_retrieval_quality(
        case=EvaluationDatasetCase(
            case_id="empty",
            question="Question?",
            expect_no_evidence=True,
        ),
        retrieved_chunk_ids=(),
        retrieved_source_document_ids=(),
        k=3,
    )

    assert metrics.empty_result_correctness == 1.0
    assert metrics.hit_rate == 1.0


def test_retrieval_quality_graded_ndcg() -> None:
    metrics = evaluate_retrieval_quality(
        case=_case(grades={ID1: 3, ID2: 1}),
        retrieved_chunk_ids=(ID2, ID1),
        retrieved_source_document_ids=(DOC2, DOC1),
        k=2,
    )

    assert metrics.ndcg == pytest.approx(0.7098, abs=0.001)


def test_citation_quality_detects_missing_unsupported_duplicate_and_malformed() -> None:
    metrics = evaluate_citation_quality(
        expected_citation_ids=("S1", "S2"),
        observed_citation_ids=("S1", "S1", "S9", "bad"),
        evidence_citation_ids=("S1", "S2"),
        expected_source_document_ids=(DOC1, DOC2),
        cited_source_document_ids=(DOC1,),
    )

    assert metrics.citation_precision == 0.5
    assert metrics.citation_recall == 0.5
    assert metrics.unsupported_citation_count == 1
    assert metrics.duplicate_citation_count == 1
    assert metrics.malformed_citation_count == 1
    assert metrics.evidence_consistency == 0.0
    assert metrics.source_coverage == 0.5


def test_groundedness_required_facts_forbidden_claims_and_abstention() -> None:
    case = _case(
        required_facts=("refund window is 14 days", "receipt is required"),
        forbidden_claims=("refund window is 30 days",),
    )

    metrics = evaluate_groundedness(
        case=case,
        answer_text="The refund window is 14 days.",
        evidence_chunk_ids=(ID1,),
    )

    assert metrics.required_fact_coverage == 0.5
    assert metrics.forbidden_claim_score == 1.0
    assert metrics.abstention_correctness == 1.0
    assert metrics.evidence_coverage == 1.0


def test_groundedness_correct_abstention() -> None:
    case = EvaluationDatasetCase(
        case_id="abstain",
        question="Question?",
        expect_no_evidence=True,
        expect_abstention=True,
    )

    metrics = evaluate_groundedness(
        case=case,
        answer_text="I do not have enough evidence to answer.",
        evidence_chunk_ids=(),
    )

    assert metrics.abstention_correctness == 1.0


def _case(
    *,
    expected: tuple[UUID, ...] = (ID1,),
    grades: dict[UUID, int] | None = None,
    required_facts: tuple[str, ...] = ("fact",),
    forbidden_claims: tuple[str, ...] = (),
) -> EvaluationDatasetCase:
    return EvaluationDatasetCase(
        case_id="case",
        question="Question?",
        expected_chunk_ids=expected,
        expected_source_document_ids=(DOC1,),
        expected_citation_ids=("S1",),
        relevance_grades=grades or {},
        required_facts=required_facts,
        forbidden_claims=forbidden_claims,
    )
