from datetime import datetime, timezone
from uuid import UUID

import pytest

from loreforge.observability import (
    InMemoryMetricsRecorder,
    RequestTrace,
    StageMetric,
    summarize_latencies,
    summarize_operation,
)

REQ1 = UUID("00000000-0000-0000-0000-000000000001")
REQ2 = UUID("00000000-0000-0000-0000-000000000002")
REQ3 = UUID("00000000-0000-0000-0000-000000000003")
REQ4 = UUID("00000000-0000-0000-0000-000000000004")
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_one_trace_summary() -> None:
    summary = summarize_latencies((_trace(REQ1, 10.0),))
    assert summary.count == 1
    assert summary.p50_ms == 10.0
    assert summary.p95_ms == 10.0


def test_multiple_trace_summary() -> None:
    summary = summarize_latencies((_trace(REQ1, 10.0), _trace(REQ2, 30.0)))
    assert summary.count == 2


def test_minimum_and_maximum() -> None:
    summary = summarize_latencies((_trace(REQ1, 30.0), _trace(REQ2, 10.0)))
    assert summary.minimum_ms == 10.0
    assert summary.maximum_ms == 30.0


def test_arithmetic_mean() -> None:
    summary = summarize_latencies((_trace(REQ1, 10.0), _trace(REQ2, 20.0)))
    assert summary.mean_ms == pytest.approx(15.0)


def test_nearest_rank_p50() -> None:
    traces = (
        _trace(REQ1, 10.0),
        _trace(REQ2, 20.0),
        _trace(REQ3, 30.0),
        _trace(REQ4, 40.0),
    )
    assert summarize_latencies(traces).p50_ms == 20.0


def test_nearest_rank_p95() -> None:
    traces = (
        _trace(REQ1, 10.0),
        _trace(REQ2, 20.0),
        _trace(REQ3, 30.0),
        _trace(REQ4, 40.0),
    )
    assert summarize_latencies(traces).p95_ms == 40.0


def test_unsorted_input() -> None:
    traces = (
        _trace(REQ1, 40.0),
        _trace(REQ2, 10.0),
        _trace(REQ3, 30.0),
        _trace(REQ4, 20.0),
    )
    summary = summarize_latencies(traces)
    assert summary.minimum_ms == 10.0
    assert summary.maximum_ms == 40.0


def test_empty_tuple_rejected() -> None:
    with pytest.raises(ValueError, match="traces"):
        summarize_latencies(())


def test_repeated_summary_is_deterministic() -> None:
    traces = (_trace(REQ1, 10.0), _trace(REQ2, 20.0))
    assert summarize_latencies(traces) == summarize_latencies(traces)


def test_input_unchanged() -> None:
    traces = (_trace(REQ1, 10.0),)
    before = traces
    summarize_latencies(traces)
    assert traces == before


def test_operation_summary() -> None:
    recorder = _recorder()
    assert summarize_operation(recorder=recorder, operation="ask").count == 2


def test_success_only_operation_summary() -> None:
    recorder = _recorder()
    summary = summarize_operation(recorder=recorder, operation="ask", success=True)
    assert summary.count == 1
    assert summary.minimum_ms == 10.0


def test_failure_only_operation_summary() -> None:
    recorder = _recorder()
    summary = summarize_operation(recorder=recorder, operation="ask", success=False)
    assert summary.count == 1
    assert summary.minimum_ms == 20.0


def test_missing_operation_rejected() -> None:
    with pytest.raises(ValueError, match="no traces"):
        summarize_operation(recorder=_recorder(), operation="missing")


def test_recorder_state_unchanged() -> None:
    recorder = _recorder()
    before = recorder.snapshot()
    summarize_operation(recorder=recorder, operation="ask")
    assert recorder.snapshot() == before


def _recorder() -> InMemoryMetricsRecorder:
    recorder = InMemoryMetricsRecorder()
    recorder.record(_trace(REQ1, 10.0, operation="ask", success=True))
    recorder.record(_trace(REQ2, 20.0, operation="ask", success=False))
    recorder.record(_trace(REQ3, 30.0, operation="ingest", success=True))
    return recorder


def _trace(
    request_id: UUID,
    duration_ms: float,
    *,
    operation: str = "ask",
    success: bool = True,
) -> RequestTrace:
    error_type = None if success else "ValueError"
    return RequestTrace(
        request_id=request_id,
        operation=operation,
        started_at=START,
        duration_ms=duration_ms,
        success=success,
        stages=(StageMetric("stage", 1.0, success, error_type),),
        error_type=error_type,
    )
