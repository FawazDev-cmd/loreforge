from datetime import datetime, timezone
from uuid import UUID

import pytest

from loreforge.observability import (
    InMemoryMetricsRecorder,
    MetricsRecorder,
    MetricsRecorderError,
    RequestTrace,
    StageMetric,
)

REQ1 = UUID("00000000-0000-0000-0000-000000000001")
REQ2 = UUID("00000000-0000-0000-0000-000000000002")
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_compatible_recorder_satisfies_protocol() -> None:
    assert isinstance(InMemoryMetricsRecorder(), MetricsRecorder)


def test_empty_initial_snapshot() -> None:
    assert InMemoryMetricsRecorder().snapshot() == ()


def test_record_one_trace() -> None:
    recorder = InMemoryMetricsRecorder()
    trace = _trace(REQ1)
    recorder.record(trace)
    assert recorder.snapshot() == (trace,)


def test_insertion_order_preserved() -> None:
    recorder = InMemoryMetricsRecorder()
    first = _trace(REQ1)
    second = _trace(REQ2, operation="other")
    recorder.record(first)
    recorder.record(second)
    assert recorder.snapshot() == (first, second)


def test_duplicate_request_id_rejected() -> None:
    recorder = InMemoryMetricsRecorder()
    recorder.record(_trace(REQ1))
    with pytest.raises(MetricsRecorderError, match="request_id"):
        recorder.record(_trace(REQ1, operation="other"))


def test_duplicate_failure_leaves_state_unchanged() -> None:
    recorder = InMemoryMetricsRecorder()
    trace = _trace(REQ1)
    recorder.record(trace)
    before = recorder.snapshot()
    with pytest.raises(MetricsRecorderError):
        recorder.record(_trace(REQ1))
    assert recorder.snapshot() == before


def test_snapshot_is_tuple() -> None:
    assert isinstance(InMemoryMetricsRecorder().snapshot(), tuple)


def test_operation_filtering() -> None:
    recorder = _recorder_with_traces()
    assert [trace.operation for trace in recorder.filter(operation="ask")] == ["ask"]


def test_success_filtering() -> None:
    recorder = _recorder_with_traces()
    assert [trace.success for trace in recorder.filter(success=False)] == [False]


def test_combined_filtering() -> None:
    recorder = _recorder_with_traces()
    assert [
        trace.request_id for trace in recorder.filter(operation="ask", success=True)
    ] == [REQ1]


def test_blank_operation_filter_rejected() -> None:
    with pytest.raises(ValueError, match="operation"):
        InMemoryMetricsRecorder().filter(operation=" ")


def test_non_boolean_success_filter_rejected() -> None:
    with pytest.raises(ValueError, match="success"):
        InMemoryMetricsRecorder().filter(success=1)  # type: ignore[arg-type]


def test_no_match_filter_returns_empty_tuple() -> None:
    assert _recorder_with_traces().filter(operation="missing") == ()


def test_returned_snapshots_do_not_expose_internal_state() -> None:
    recorder = InMemoryMetricsRecorder()
    trace = _trace(REQ1)
    recorder.record(trace)
    snapshot = recorder.snapshot()
    snapshot += (_trace(REQ2),)
    assert recorder.snapshot() == (trace,)


def _recorder_with_traces() -> InMemoryMetricsRecorder:
    recorder = InMemoryMetricsRecorder()
    recorder.record(_trace(REQ1, operation="ask", success=True))
    recorder.record(
        _trace(REQ2, operation="ingest", success=False, error_type="ValueError")
    )
    return recorder


def _trace(
    request_id: UUID,
    *,
    operation: str = "ask",
    success: bool = True,
    error_type: str | None = None,
) -> RequestTrace:
    stages = (StageMetric("stage", 1.0, success, None if success else error_type),)
    return RequestTrace(request_id, operation, START, 10.0, success, stages, error_type)
