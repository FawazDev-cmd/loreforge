from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from math import inf, nan
from uuid import UUID

import pytest

from loreforge.observability import (
    LatencySummary,
    RequestTrace,
    RuntimeQueryObservation,
    StageMetric,
)

REQ1 = UUID("00000000-0000-0000-0000-000000000001")
REQ2 = UUID("00000000-0000-0000-0000-000000000002")
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_stage_metric_successful_stage() -> None:
    metric = StageMetric("retrieve", 1.0, True)
    assert metric.error_type is None


def test_stage_metric_failed_stage() -> None:
    metric = StageMetric("retrieve", 1.0, False, "ValueError")
    assert metric.error_type == "ValueError"


@pytest.mark.parametrize("name", ["", "   "])
def test_stage_metric_blank_name_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="name"):
        StageMetric(name, 1.0, True)


@pytest.mark.parametrize("duration", [1, True])
def test_stage_metric_invalid_duration_types(duration: object) -> None:
    with pytest.raises(ValueError, match="duration_ms"):
        StageMetric("stage", duration, True)  # type: ignore[arg-type]


@pytest.mark.parametrize("duration", [-1.0, nan, inf, -inf])
def test_stage_metric_negative_and_non_finite_duration_rejected(
    duration: float,
) -> None:
    with pytest.raises(ValueError):
        StageMetric("stage", duration, True)


def test_stage_metric_boolean_success_rejected() -> None:
    with pytest.raises(ValueError, match="success"):
        StageMetric("stage", 1.0, 1)  # type: ignore[arg-type]


def test_stage_metric_success_with_error_type_rejected() -> None:
    with pytest.raises(ValueError, match="error_type"):
        StageMetric("stage", 1.0, True, "ValueError")


def test_stage_metric_failed_without_error_type_rejected() -> None:
    with pytest.raises(ValueError, match="error_type"):
        StageMetric("stage", 1.0, False)


def test_stage_metric_failed_with_blank_error_type_rejected() -> None:
    with pytest.raises(ValueError, match="error_type"):
        StageMetric("stage", 1.0, False, " ")


def test_stage_metric_is_immutable() -> None:
    metric = StageMetric("stage", 1.0, True)
    with pytest.raises(FrozenInstanceError):
        metric.name = "changed"


def test_request_trace_valid_successful_trace() -> None:
    trace = _trace(stages=(StageMetric("stage", 1.0, True),))
    assert trace.success is True


def test_request_trace_valid_failed_trace() -> None:
    trace = _trace(success=False, error_type="RuntimeError")
    assert trace.error_type == "RuntimeError"


def test_request_trace_valid_empty_stage_trace() -> None:
    trace = _trace(stages=())
    assert trace.stages == ()


def test_request_trace_blank_operation_rejected() -> None:
    with pytest.raises(ValueError, match="operation"):
        _trace(operation=" ")


def test_request_trace_naive_timestamp_rejected() -> None:
    with pytest.raises(ValueError, match="timezone"):
        _trace(started_at=datetime(2026, 1, 1))


def test_request_trace_non_utc_timestamp_rejected() -> None:
    with pytest.raises(ValueError, match="UTC"):
        _trace(started_at=datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=1))))


def test_request_trace_invalid_duration_rejected() -> None:
    with pytest.raises(ValueError, match="duration_ms"):
        _trace(duration_ms=True)  # type: ignore[arg-type]


def test_request_trace_duplicate_stage_names_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        _trace(
            stages=(StageMetric("stage", 1.0, True), StageMetric("stage", 2.0, True))
        )


def test_request_trace_total_duration_below_stage_duration_rejected() -> None:
    with pytest.raises(ValueError, match="duration"):
        _trace(duration_ms=1.0, stages=(StageMetric("stage", 2.0, True),))


def test_request_trace_success_with_failed_stage_rejected() -> None:
    with pytest.raises(ValueError, match="failed"):
        _trace(stages=(StageMetric("stage", 1.0, False, "ValueError"),))


def test_request_trace_success_with_error_type_rejected() -> None:
    with pytest.raises(ValueError, match="error_type"):
        _trace(error_type="ValueError")


def test_request_trace_failure_without_error_or_failed_stage_rejected() -> None:
    with pytest.raises(ValueError, match="failed"):
        _trace(success=False, error_type=None)


def test_request_trace_order_preserved() -> None:
    stages = (StageMetric("one", 1.0, True), StageMetric("two", 2.0, True))
    assert _trace(stages=stages).stages == stages


def test_request_trace_is_immutable() -> None:
    trace = _trace()
    with pytest.raises(FrozenInstanceError):
        trace.operation = "changed"


def test_latency_summary_valid_values() -> None:
    summary = LatencySummary(2, 1.0, 3.0, 2.0, 1.0, 3.0)
    assert summary.count == 2


@pytest.mark.parametrize("count", [0, -1, 1.2, True])
def test_latency_summary_invalid_count_rejected(count: object) -> None:
    with pytest.raises(ValueError, match="count"):
        LatencySummary(count, 1.0, 1.0, 1.0, 1.0, 1.0)  # type: ignore[arg-type]


def test_latency_summary_invalid_float_type_rejected() -> None:
    with pytest.raises(ValueError, match="minimum_ms"):
        LatencySummary(1, 1, 1.0, 1.0, 1.0, 1.0)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [-1.0, nan, inf])
def test_latency_summary_non_finite_and_negative_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        LatencySummary(1, value, 1.0, 1.0, 1.0, 1.0)


def test_latency_summary_ordering_invariants_rejected() -> None:
    with pytest.raises(ValueError, match="mean"):
        LatencySummary(1, 2.0, 3.0, 1.0, 2.0, 3.0)
    with pytest.raises(ValueError, match="p50"):
        LatencySummary(1, 1.0, 3.0, 2.0, 4.0, 3.0)
    with pytest.raises(ValueError, match="p95"):
        LatencySummary(1, 1.0, 3.0, 2.0, 2.0, 4.0)
    with pytest.raises(ValueError, match="p50"):
        LatencySummary(1, 1.0, 3.0, 2.0, 3.0, 2.0)


def test_latency_summary_is_immutable() -> None:
    summary = LatencySummary(1, 1.0, 1.0, 1.0, 1.0, 1.0)
    with pytest.raises(FrozenInstanceError):
        summary.count = 2


def _trace(
    *,
    request_id: UUID = REQ1,
    operation: str = "ask",
    started_at: datetime = START,
    duration_ms: float = 10.0,
    success: bool = True,
    stages: tuple[StageMetric, ...] = (StageMetric("stage", 1.0, True),),
    error_type: str | None = None,
    observation: RuntimeQueryObservation | None = None,
) -> RequestTrace:
    return RequestTrace(
        request_id,
        operation,
        started_at,
        duration_ms,
        success,
        stages,
        error_type,
        observation,
    )


def test_runtime_query_observation_accepts_safe_metadata() -> None:
    observation = RuntimeQueryObservation(
        semantic_result_count=2,
        lexical_result_count=1,
        fused_result_count=2,
        reranked_result_count=1,
        evidence_count=1,
        citation_count=1,
        citations_valid=True,
        citation_precision=1.0,
        citation_recall=1.0,
        provider_model="offline-model",
        finish_reason="stop",
    )

    assert observation.provider_model == "offline-model"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("semantic_result_count", -1),
        ("citation_count", 1.2),
        ("citations_valid", 1),
        ("citation_precision", 1.1),
        ("citation_recall", -0.1),
        ("provider_model", " "),
        ("finish_reason", " "),
        ("failure_category", " "),
    ],
)
def test_runtime_query_observation_rejects_invalid_metadata(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        RuntimeQueryObservation(**{field: value})


def test_request_trace_can_include_runtime_observation() -> None:
    observation = RuntimeQueryObservation(semantic_result_count=1)
    trace = _trace(observation=observation)

    assert trace.observation is observation
