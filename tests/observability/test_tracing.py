from datetime import datetime, timezone
from uuid import UUID

import pytest

from loreforge.observability import (
    InMemoryMetricsRecorder,
    RequestTracer,
    RequestTracingError,
)

REQ1 = UUID("00000000-0000-0000-0000-000000000001")
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeMonotonicClock:
    def __init__(self, values: tuple[float, ...]) -> None:
        self.values = list(values)
        self.calls = 0

    def now(self) -> float:
        self.calls += 1
        return self.values.pop(0)


class FakeUtcClock:
    def __init__(self) -> None:
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        return START


def test_constructor_records_nothing() -> None:
    recorder = InMemoryMetricsRecorder()
    RequestTracer(
        operation="ask",
        recorder=recorder,
        monotonic_clock=FakeMonotonicClock((1.0,)),
        utc_clock=FakeUtcClock(),
    )
    assert recorder.snapshot() == ()


def test_supplied_request_id_preserved() -> None:
    tracer = _tracer(clock_values=(1.0,))
    assert tracer.request_id == REQ1


def test_generated_request_id_is_uuid() -> None:
    tracer = RequestTracer(
        operation="ask",
        recorder=InMemoryMetricsRecorder(),
        monotonic_clock=FakeMonotonicClock((1.0,)),
        utc_clock=FakeUtcClock(),
    )
    assert isinstance(tracer.request_id, UUID)


def test_start_clocks_called_once() -> None:
    monotonic = FakeMonotonicClock((1.0,))
    utc = FakeUtcClock()
    RequestTracer(
        operation="ask",
        recorder=InMemoryMetricsRecorder(),
        monotonic_clock=monotonic,
        utc_clock=utc,
    )
    assert monotonic.calls == 1
    assert utc.calls == 1


def test_one_successful_stage() -> None:
    tracer = _tracer(clock_values=(1.0, 2.0, 2.5, 3.0))
    with tracer.stage("retrieve"):
        pass
    trace = tracer.finish_success()
    assert trace.stages[0].name == "retrieve"
    assert trace.stages[0].success is True


def test_multiple_successful_stages_preserve_completion_order() -> None:
    tracer = _tracer(clock_values=(1.0, 2.0, 3.0, 4.0, 6.0, 7.0))
    with tracer.stage("one"):
        pass
    with tracer.stage("two"):
        pass
    trace = tracer.finish_success()
    assert [stage.name for stage in trace.stages] == ["one", "two"]


def test_successful_request_finish_records_once() -> None:
    recorder = InMemoryMetricsRecorder()
    tracer = _tracer(clock_values=(1.0, 2.0), recorder=recorder)
    trace = tracer.finish_success()
    assert recorder.snapshot() == (trace,)


def test_exact_millisecond_conversion() -> None:
    tracer = _tracer(clock_values=(1.0, 1.25, 1.75, 2.0))
    with tracer.stage("stage"):
        pass
    trace = tracer.finish_success()
    assert trace.stages[0].duration_ms == 500.0
    assert trace.duration_ms == 1000.0


def test_failed_stage_records_exception_class_and_reraises() -> None:
    tracer = _tracer(clock_values=(1.0, 2.0, 2.5, 3.0))
    error = RuntimeError("secret")
    with pytest.raises(RuntimeError) as raised:
        with tracer.stage("stage"):
            raise error
    assert raised.value is error
    trace = tracer.finish_failure(error)
    assert trace.stages[0].error_type == "RuntimeError"


def test_failed_request_finish() -> None:
    tracer = _tracer(clock_values=(1.0, 2.0))
    trace = tracer.finish_failure(ValueError)
    assert trace.success is False
    assert trace.error_type == "ValueError"


def test_exception_message_absent_from_trace() -> None:
    tracer = _tracer(clock_values=(1.0, 2.0, 2.5, 3.0))
    error = RuntimeError("very secret")
    with pytest.raises(RuntimeError):
        with tracer.stage("stage"):
            raise error
    trace = tracer.finish_failure(error)
    assert "very secret" not in str(trace)


def test_duplicate_stage_rejected() -> None:
    tracer = _tracer(clock_values=(1.0, 2.0, 3.0))
    with tracer.stage("stage"):
        pass
    with pytest.raises(RequestTracingError, match="stage"):
        with tracer.stage("stage"):
            pass


def test_blank_stage_rejected() -> None:
    with pytest.raises(ValueError, match="stage"):
        with _tracer(clock_values=(1.0,)).stage(" "):
            pass


def test_stage_after_finish_rejected() -> None:
    tracer = _tracer(clock_values=(1.0, 2.0))
    tracer.finish_success()
    with pytest.raises(RequestTracingError, match="finish"):
        with tracer.stage("late"):
            pass


def test_double_finish_rejected() -> None:
    tracer = _tracer(clock_values=(1.0, 2.0))
    tracer.finish_success()
    with pytest.raises(RequestTracingError, match="finished"):
        tracer.finish_success()


def test_finish_while_stage_active_rejected() -> None:
    tracer = _tracer(clock_values=(1.0, 2.0, 3.0))
    with pytest.raises(RequestTracingError, match="active"):
        with tracer.stage("stage"):
            tracer.finish_success()


def test_success_finish_after_failed_stage_rejected() -> None:
    tracer = _tracer(clock_values=(1.0, 2.0, 3.0))
    with pytest.raises(RuntimeError):
        with tracer.stage("stage"):
            raise RuntimeError("secret")
    with pytest.raises(RequestTracingError, match="failed"):
        tracer.finish_success()


def test_backwards_stage_clock_rejected() -> None:
    tracer = _tracer(clock_values=(2.0, 3.0, 2.5))
    with pytest.raises(RequestTracingError, match="backwards"):
        with tracer.stage("stage"):
            pass


def test_backwards_request_clock_rejected() -> None:
    tracer = _tracer(clock_values=(2.0, 1.0))
    with pytest.raises(RequestTracingError, match="backwards"):
        tracer.finish_success()


def test_operation_exception_identity_preserved() -> None:
    tracer = _tracer(clock_values=(1.0, 2.0, 3.0))
    error = KeyError("secret")
    with pytest.raises(KeyError) as raised:
        with tracer.stage("stage"):
            raise error
    assert raised.value is error


def test_deterministic_behavior_with_fake_clocks() -> None:
    first = _finished_trace()
    second = _finished_trace()
    assert first.duration_ms == second.duration_ms
    assert first.stages == second.stages


def _finished_trace():
    tracer = _tracer(clock_values=(1.0, 2.0, 3.0, 4.0))
    with tracer.stage("stage"):
        pass
    return tracer.finish_success()


def _tracer(
    *,
    clock_values: tuple[float, ...],
    recorder: InMemoryMetricsRecorder | None = None,
) -> RequestTracer:
    return RequestTracer(
        operation="ask",
        recorder=recorder or InMemoryMetricsRecorder(),
        request_id=REQ1,
        monotonic_clock=FakeMonotonicClock(clock_values),
        utc_clock=FakeUtcClock(),
    )
