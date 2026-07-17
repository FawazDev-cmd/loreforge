from uuid import UUID

import pytest

from loreforge.evaluation import (
    AnswerMetrics,
    EvaluationCase,
    EvaluationCaseResult,
    RetrievalMetrics,
    build_evaluation_report,
    evaluate_case,
)
from loreforge.generation import (
    CitationValidationResult,
    EvidenceContext,
    EvidenceItem,
    GroundedAnswer,
    SourceReference,
    ValidatedGroundedAnswer,
)

ID1 = UUID("00000000-0000-0000-0000-000000000001")
ID2 = UUID("00000000-0000-0000-0000-000000000002")
ID3 = UUID("00000000-0000-0000-0000-000000000003")
DOC1 = UUID("00000000-0000-0000-0000-000000000101")
DOC2 = UUID("00000000-0000-0000-0000-000000000102")


def test_evaluate_case_successful_full_evaluation() -> None:
    result = evaluate_case(
        case=_case(), retrieved_chunk_ids=(ID1, ID2), answer=_answer(), k=2
    )

    assert result.retrieval.hit_rate == 1.0
    assert result.answer.citation_precision == 1.0


def test_evaluate_case_preserves_case_id() -> None:
    result = evaluate_case(
        case=_case(case_id="case-x"), retrieved_chunk_ids=(ID1,), answer=_answer(), k=1
    )

    assert result.case_id == "case-x"


def test_evaluate_case_preserves_configured_k() -> None:
    result = evaluate_case(
        case=_case(), retrieved_chunk_ids=(ID1,), answer=_answer(), k=7
    )

    assert result.retrieval.k == 7


def test_evaluate_case_retrieval_metrics_are_correct() -> None:
    result = evaluate_case(
        case=_case(relevant=(ID2,)),
        retrieved_chunk_ids=(ID1, ID2),
        answer=_answer(),
        k=2,
    )

    assert result.retrieval.precision == 0.5
    assert result.retrieval.reciprocal_rank == 0.5


def test_evaluate_case_answer_metrics_are_correct() -> None:
    result = evaluate_case(
        case=_case(expected_answer="Answer."),
        retrieved_chunk_ids=(ID1,),
        answer=_answer(answer_text="Answer. [S1]"),
        k=1,
    )

    assert result.answer.normalized_exact_match == 1.0


def test_evaluate_case_rejects_mismatched_question() -> None:
    with pytest.raises(ValueError, match="question"):
        evaluate_case(
            case=_case(question="Question?"),
            retrieved_chunk_ids=(ID1,),
            answer=_answer(question="Different?"),
            k=1,
        )


def test_evaluate_case_is_deterministic() -> None:
    kwargs = {
        "case": _case(),
        "retrieved_chunk_ids": (ID1,),
        "answer": _answer(),
        "k": 1,
    }

    assert evaluate_case(**kwargs) == evaluate_case(**kwargs)


def test_evaluate_case_inputs_remain_unchanged() -> None:
    case = _case()
    retrieved = (ID1,)
    answer = _answer()
    before = (case, retrieved, answer)

    evaluate_case(case=case, retrieved_chunk_ids=retrieved, answer=answer, k=1)

    assert (case, retrieved, answer) == before


def test_build_report_one_result() -> None:
    result = _result("case-1")

    report = build_evaluation_report((result,))

    assert report.results == (result,)
    assert report.mean_hit_rate == result.retrieval.hit_rate


def test_build_report_multiple_result_means() -> None:
    first = _result("case-1", retrieval=RetrievalMetrics(2, 1.0, 0.5, 1.0, 1.0))
    second = _result("case-2", retrieval=RetrievalMetrics(2, 0.0, 0.0, 0.0, 0.0))

    report = build_evaluation_report((first, second))

    assert report.mean_hit_rate == pytest.approx(0.5)
    assert report.mean_precision == pytest.approx(0.25)
    assert report.mean_recall == pytest.approx(0.5)
    assert report.mean_reciprocal_rank == pytest.approx(0.5)


def test_build_report_preserves_result_order() -> None:
    first = _result("case-1")
    second = _result("case-2")

    report = build_evaluation_report((first, second))

    assert report.results == (first, second)


def test_build_report_mixed_exact_match_values_average_only_present_values() -> None:
    first = _result("case-1", answer=AnswerMetrics(1.0, 1.0, 1.0))
    second = _result("case-2", answer=AnswerMetrics(1.0, 1.0, None))
    third = _result("case-3", answer=AnswerMetrics(1.0, 1.0, 0.0))

    report = build_evaluation_report((first, second, third))

    assert report.mean_normalized_exact_match == pytest.approx(0.5)


def test_build_report_all_exact_match_values_absent_returns_none() -> None:
    first = _result("case-1", answer=AnswerMetrics(1.0, 1.0, None))
    second = _result("case-2", answer=AnswerMetrics(1.0, 1.0, None))

    report = build_evaluation_report((first, second))

    assert report.mean_normalized_exact_match is None


def test_build_report_rejects_empty_results() -> None:
    with pytest.raises(ValueError, match="results"):
        build_evaluation_report(())


def test_build_report_rejects_duplicate_case_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        build_evaluation_report((_result("case-1"), _result("case-1")))


def test_build_report_is_deterministic() -> None:
    results = (_result("case-1"), _result("case-2"))

    assert build_evaluation_report(results) == build_evaluation_report(results)


def test_build_report_inputs_remain_unchanged() -> None:
    results = (_result("case-1"),)
    before = results

    build_evaluation_report(results)

    assert results == before


def _case(
    *,
    case_id: str = "case-1",
    question: str = "Question?",
    relevant: tuple[UUID, ...] = (ID1,),
    expected_answer: str | None = "Answer.",
) -> EvaluationCase:
    return EvaluationCase(case_id, question, relevant, ("S1",), expected_answer)


def _answer(
    *, question: str = "Question?", answer_text: str = "Answer. [S1]"
) -> ValidatedGroundedAnswer:
    source = SourceReference("S1", DOC1, ID1, "S1.pdf", 1)
    item = EvidenceItem("S1", ID1, DOC1, "S1.pdf", 1, "Evidence", 1.0, 1)
    rendered = "[S1]\nSource: S1.pdf\nPage: 1\nContent:\nEvidence"
    evidence = EvidenceContext((item,), rendered, len(rendered), False)
    grounded = GroundedAnswer(
        question, answer_text, (source,), evidence, "model", "stop", True
    )
    validation = CitationValidationResult(("S1",), ("S1",), (), False, True)
    return ValidatedGroundedAnswer(grounded, validation, (source,))


def _result(
    case_id: str,
    *,
    retrieval: RetrievalMetrics | None = None,
    answer: AnswerMetrics | None = None,
) -> EvaluationCaseResult:
    return EvaluationCaseResult(
        case_id,
        retrieval or RetrievalMetrics(2, 1.0, 0.5, 1.0, 1.0),
        answer or AnswerMetrics(1.0, 1.0, 1.0),
    )
