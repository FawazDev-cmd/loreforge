from json import loads
from pathlib import Path

from loreforge.evaluation import (
    EXIT_CONFIGURATION_ERROR,
    EXIT_REGRESSION,
    EXIT_SUCCESS,
    EvaluationThresholds,
    evaluate_gate,
    human_report,
    load_dataset,
    load_thresholds,
    run_fixture_evaluation,
)
from loreforge.evaluation.cli import main
from loreforge.evaluation.gate import thresholds_from_dict

GOLDEN = Path("tests/fixtures/evaluation/golden_dataset.json")
DEGRADED = Path("tests/fixtures/evaluation/degraded_dataset.json")
THRESHOLDS = Path("tests/fixtures/evaluation/thresholds.json")


def test_golden_fixture_passes_regression_gate() -> None:
    report = run_fixture_evaluation(
        dataset=load_dataset(GOLDEN),
        thresholds=load_thresholds(THRESHOLDS),
    )

    assert report.passed is True
    assert report.failed_thresholds == ()
    assert report.aggregates["mean_hit_rate_at_k"] == 1.0
    assert report.aggregates["mean_citation_coverage"] == 1.0
    assert report.tag_summaries["citation"]["case_count"] == 2.0


def test_degraded_fixture_fails_regression_gate() -> None:
    report = run_fixture_evaluation(
        dataset=load_dataset(DEGRADED),
        thresholds=load_thresholds(THRESHOLDS),
    )

    assert report.passed is False
    assert "mean_hit_rate_at_k" in report.failed_thresholds
    assert report.cases[0]["failure_reasons"] == [
        "retrieval",
        "citation",
        "groundedness",
    ]


def test_report_omits_raw_question_answer_and_secret_like_values() -> None:
    report = run_fixture_evaluation(
        dataset=load_dataset(GOLDEN),
        thresholds=load_thresholds(THRESHOLDS),
    )
    payload = report.to_json()

    assert "What is the refund window" not in payload
    assert "The refund window is 14 days" not in payload
    assert "api_key" not in payload.casefold()
    assert "postgres://" not in payload.casefold()


def test_human_report_highlights_failed_cases() -> None:
    report = run_fixture_evaluation(
        dataset=load_dataset(DEGRADED),
        thresholds=load_thresholds(THRESHOLDS),
    )

    text = human_report(report)

    assert "Evaluation: FAIL" in text
    assert "exact-lexical-refund-window" in text
    assert "retrieval; citation; groundedness" in text


def test_threshold_boundary_equality_passes() -> None:
    result = evaluate_gate(
        aggregates={
            "mean_hit_rate_at_k": 1.0,
            "mean_recall_at_k": 1.0,
            "mean_mrr": 1.0,
            "mean_ndcg_at_k": 1.0,
            "mean_citation_validity": 1.0,
            "mean_citation_coverage": 1.0,
            "mean_required_fact_coverage": 1.0,
            "mean_abstention_correctness": 1.0,
            "error_count": 0.0,
        },
        thresholds=EvaluationThresholds(),
    )

    assert result.passed is True


def test_invalid_threshold_ranges_fail_validation() -> None:
    try:
        thresholds_from_dict({"min_mrr": 1.5})
    except ValueError as exc:
        assert "min_mrr" in str(exc)
    else:
        raise AssertionError("expected invalid threshold failure")


def test_cli_passing_fixture_returns_zero_and_writes_json(tmp_path: Path) -> None:
    output = tmp_path / "report.json"

    exit_code = main(
        [
            "--dataset",
            str(GOLDEN),
            "--thresholds",
            str(THRESHOLDS),
            "--output",
            str(output),
        ]
    )

    assert exit_code == EXIT_SUCCESS
    assert loads(output.read_text(encoding="utf-8"))["passed"] is True


def test_cli_degraded_fixture_returns_regression_code(tmp_path: Path) -> None:
    output = tmp_path / "report.json"

    exit_code = main(
        [
            "--dataset",
            str(DEGRADED),
            "--thresholds",
            str(THRESHOLDS),
            "--output",
            str(output),
        ]
    )

    assert exit_code == EXIT_REGRESSION
    assert loads(output.read_text(encoding="utf-8"))["passed"] is False


def test_cli_configuration_error_has_distinct_exit_code(tmp_path: Path) -> None:
    output = tmp_path / "report.json"

    exit_code = main(
        [
            "--dataset",
            "missing.json",
            "--thresholds",
            str(THRESHOLDS),
            "--output",
            str(output),
        ]
    )

    assert exit_code == EXIT_CONFIGURATION_ERROR
    assert not output.exists()
