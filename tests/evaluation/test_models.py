from dataclasses import FrozenInstanceError
from math import inf, nan
from uuid import UUID

import pytest

from loreforge.evaluation import (
    AnswerMetrics,
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationReport,
    RetrievalMetrics,
)

ID1 = UUID("00000000-0000-0000-0000-000000000001")
ID2 = UUID("00000000-0000-0000-0000-000000000002")


def test_evaluation_case_accepts_expected_answer() -> None:
    case = EvaluationCase("case-1", "Question?", (ID1,), ("S1",), "Answer")

    assert case.expected_answer == "Answer"


def test_evaluation_case_accepts_missing_expected_answer() -> None:
    case = EvaluationCase("case-1", "Question?", (ID1,), ("S1",))

    assert case.expected_answer is None


def test_evaluation_case_accepts_empty_expected_citations() -> None:
    case = EvaluationCase("case-1", "Question?", (ID1,), ())

    assert case.expected_citation_ids == ()


@pytest.mark.parametrize("case_id", ["", "   "])
def test_evaluation_case_rejects_blank_case_id(case_id: str) -> None:
    with pytest.raises(ValueError, match="case_id"):
        EvaluationCase(case_id, "Question?", (ID1,), ("S1",))


@pytest.mark.parametrize("question", ["", "   "])
def test_evaluation_case_rejects_blank_question(question: str) -> None:
    with pytest.raises(ValueError, match="question"):
        EvaluationCase("case-1", question, (ID1,), ("S1",))


def test_evaluation_case_rejects_empty_relevant_ids() -> None:
    with pytest.raises(ValueError, match="relevant_chunk_ids"):
        EvaluationCase("case-1", "Question?", (), ("S1",))


def test_evaluation_case_rejects_duplicate_relevant_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        EvaluationCase("case-1", "Question?", (ID1, ID1), ("S1",))


def test_evaluation_case_rejects_malformed_citation_id() -> None:
    with pytest.raises(ValueError, match="expected_citation_ids"):
        EvaluationCase("case-1", "Question?", (ID1,), ("S0",))


def test_evaluation_case_rejects_duplicate_expected_citation_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        EvaluationCase("case-1", "Question?", (ID1,), ("S1", "S1"))


@pytest.mark.parametrize("expected_answer", ["", "   "])
def test_evaluation_case_rejects_blank_expected_answer(expected_answer: str) -> None:
    with pytest.raises(ValueError, match="expected_answer"):
        EvaluationCase("case-1", "Question?", (ID1,), ("S1",), expected_answer)


def test_evaluation_case_preserves_order() -> None:
    case = EvaluationCase("case-1", "Question?", (ID2, ID1), ("S2", "S1"))

    assert case.relevant_chunk_ids == (ID2, ID1)
    assert case.expected_citation_ids == ("S2", "S1")


def test_evaluation_case_is_immutable() -> None:
    case = EvaluationCase("case-1", "Question?", (ID1,), ("S1",))

    with pytest.raises(FrozenInstanceError):
        case.case_id = "changed"


def test_retrieval_metrics_accepts_boundaries() -> None:
    metrics = RetrievalMetrics(1, 0.0, 1.0, 0.5, 1.0)

    assert metrics.precision == 1.0


@pytest.mark.parametrize("k", [0, -1, 1.2])
def test_retrieval_metrics_rejects_invalid_k(k: int) -> None:
    with pytest.raises(ValueError, match="k"):
        RetrievalMetrics(k, 1.0, 1.0, 1.0, 1.0)  # type: ignore[arg-type]


def test_retrieval_metrics_rejects_boolean_k() -> None:
    with pytest.raises(ValueError, match="k"):
        RetrievalMetrics(True, 1.0, 1.0, 1.0, 1.0)  # type: ignore[arg-type]


def test_retrieval_metrics_rejects_non_float_metrics() -> None:
    with pytest.raises(ValueError, match="hit_rate"):
        RetrievalMetrics(1, 1, 1.0, 1.0, 1.0)  # type: ignore[arg-type]


def test_retrieval_metrics_rejects_boolean_metrics() -> None:
    with pytest.raises(ValueError, match="precision"):
        RetrievalMetrics(1, 1.0, True, 1.0, 1.0)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_retrieval_metrics_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        RetrievalMetrics(1, value, 1.0, 1.0, 1.0)


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_retrieval_metrics_rejects_out_of_range_values(value: float) -> None:
    with pytest.raises(ValueError, match="between"):
        RetrievalMetrics(1, 1.0, value, 1.0, 1.0)


def test_retrieval_metrics_is_immutable() -> None:
    metrics = RetrievalMetrics(1, 1.0, 1.0, 1.0, 1.0)

    with pytest.raises(FrozenInstanceError):
        metrics.k = 2


def test_answer_metrics_accepts_exact_match() -> None:
    metrics = AnswerMetrics(1.0, 1.0, 0.0)

    assert metrics.normalized_exact_match == 0.0


def test_answer_metrics_accepts_missing_exact_match() -> None:
    metrics = AnswerMetrics(1.0, 1.0, None)

    assert metrics.normalized_exact_match is None


def test_answer_metrics_rejects_invalid_types() -> None:
    with pytest.raises(ValueError, match="citation_precision"):
        AnswerMetrics(1, 1.0, None)  # type: ignore[arg-type]


def test_answer_metrics_rejects_booleans() -> None:
    with pytest.raises(ValueError, match="citation_recall"):
        AnswerMetrics(1.0, False, None)  # type: ignore[arg-type]


def test_answer_metrics_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        AnswerMetrics(1.0, 1.0, nan)


def test_answer_metrics_rejects_out_of_range_values() -> None:
    with pytest.raises(ValueError, match="between"):
        AnswerMetrics(1.0, 1.1, None)


def test_answer_metrics_is_immutable() -> None:
    metrics = AnswerMetrics(1.0, 1.0, None)

    with pytest.raises(FrozenInstanceError):
        metrics.citation_precision = 0.0


def test_evaluation_case_result_accepts_valid_values() -> None:
    result = _case_result("case-1")

    assert result.case_id == "case-1"


def test_evaluation_case_result_rejects_blank_case_id() -> None:
    with pytest.raises(ValueError, match="case_id"):
        EvaluationCaseResult(" ", _retrieval(), _answer())


def test_evaluation_case_result_is_immutable() -> None:
    result = _case_result("case-1")

    with pytest.raises(FrozenInstanceError):
        result.case_id = "changed"


def test_evaluation_report_accepts_valid_values() -> None:
    report = EvaluationReport(
        (_case_result("case-1"),), 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0
    )

    assert report.results[0].case_id == "case-1"


def test_evaluation_report_rejects_empty_results() -> None:
    with pytest.raises(ValueError, match="results"):
        EvaluationReport((), 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, None)


def test_evaluation_report_rejects_duplicate_case_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        EvaluationReport(
            (_case_result("case-1"), _case_result("case-1")),
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            None,
        )


def test_evaluation_report_rejects_invalid_mean_types() -> None:
    with pytest.raises(ValueError, match="mean_hit_rate"):
        EvaluationReport((_case_result("case-1"),), 1, 1.0, 1.0, 1.0, 1.0, 1.0, None)  # type: ignore[arg-type]


def test_evaluation_report_rejects_non_finite_means() -> None:
    with pytest.raises(ValueError, match="finite"):
        EvaluationReport((_case_result("case-1"),), nan, 1.0, 1.0, 1.0, 1.0, 1.0, None)


def test_evaluation_report_rejects_out_of_range_means() -> None:
    with pytest.raises(ValueError, match="between"):
        EvaluationReport((_case_result("case-1"),), 1.1, 1.0, 1.0, 1.0, 1.0, 1.0, None)


def test_evaluation_report_accepts_none_exact_match_mean() -> None:
    report = EvaluationReport(
        (_case_result("case-1"),), 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, None
    )

    assert report.mean_normalized_exact_match is None


def test_evaluation_report_is_immutable() -> None:
    report = EvaluationReport(
        (_case_result("case-1"),), 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, None
    )

    with pytest.raises(FrozenInstanceError):
        report.results = ()


def _retrieval() -> RetrievalMetrics:
    return RetrievalMetrics(1, 1.0, 1.0, 1.0, 1.0)


def _answer() -> AnswerMetrics:
    return AnswerMetrics(1.0, 1.0, 1.0)


def _case_result(case_id: str) -> EvaluationCaseResult:
    return EvaluationCaseResult(case_id, _retrieval(), _answer())
