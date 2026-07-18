"""Request tracing lifecycle helpers."""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID, uuid4

from loreforge.observability.clocks import (
    MonotonicClock,
    SystemMonotonicClock,
    SystemUtcClock,
    UtcClock,
)
from loreforge.observability.models import (
    RequestTrace,
    RuntimeQueryObservation,
    StageMetric,
)
from loreforge.observability.recorder import MetricsRecorder


class RequestTracingError(ValueError):
    """Raised when request tracing lifecycle rules are violated."""


class RequestTracer:
    """Trace a request and its named stages with injectable clocks."""

    def __init__(
        self,
        *,
        operation: str,
        recorder: MetricsRecorder,
        request_id: UUID | None = None,
        monotonic_clock: MonotonicClock | None = None,
        utc_clock: UtcClock | None = None,
    ) -> None:
        if not operation.strip():
            msg = "operation must not be empty"
            raise ValueError(msg)
        self.operation = operation
        self.request_id = request_id or uuid4()
        self._recorder = recorder
        self._monotonic_clock = monotonic_clock or SystemMonotonicClock()
        self._utc_clock = utc_clock or SystemUtcClock()
        self._start_monotonic = float(self._monotonic_clock.now())
        self._started_at = self._utc_clock.now()
        self._stages: list[StageMetric] = []
        self._stage_names: set[str] = set()
        self._finished = False
        self._active_stage: str | None = None

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        if not name.strip():
            msg = "stage name must not be empty"
            raise ValueError(msg)
        if self._finished:
            msg = "cannot start a stage after request finish"
            raise RequestTracingError(msg)
        if name in self._stage_names:
            msg = "stage name has already been used"
            raise RequestTracingError(msg)
        if self._active_stage is not None:
            msg = "another stage is already active"
            raise RequestTracingError(msg)
        self._stage_names.add(name)
        self._active_stage = name
        stage_start = float(self._monotonic_clock.now())
        try:
            yield
        except BaseException as error:
            duration_ms = self._elapsed_ms(
                stage_start, float(self._monotonic_clock.now())
            )
            self._stages.append(
                StageMetric(
                    name=name,
                    duration_ms=duration_ms,
                    success=False,
                    error_type=type(error).__name__,
                )
            )
            self._active_stage = None
            raise
        else:
            duration_ms = self._elapsed_ms(
                stage_start, float(self._monotonic_clock.now())
            )
            self._stages.append(
                StageMetric(name=name, duration_ms=duration_ms, success=True)
            )
            self._active_stage = None

    def finish_success(
        self, *, observation: RuntimeQueryObservation | None = None
    ) -> RequestTrace:
        self._validate_can_finish()
        if any(not stage.success for stage in self._stages):
            msg = "cannot finish successfully after a failed stage"
            raise RequestTracingError(msg)
        trace = RequestTrace(
            request_id=self.request_id,
            operation=self.operation,
            started_at=self._started_at,
            duration_ms=self._request_duration_ms(),
            success=True,
            stages=tuple(self._stages),
            observation=observation,
        )
        return self._record_finished(trace)

    def finish_failure(
        self,
        error: BaseException | type[BaseException],
        *,
        observation: RuntimeQueryObservation | None = None,
    ) -> RequestTrace:
        self._validate_can_finish()
        error_type = error.__name__ if isinstance(error, type) else type(error).__name__
        trace = RequestTrace(
            request_id=self.request_id,
            operation=self.operation,
            started_at=self._started_at,
            duration_ms=self._request_duration_ms(),
            success=False,
            stages=tuple(self._stages),
            error_type=error_type,
            observation=observation,
        )
        return self._record_finished(trace)

    def _validate_can_finish(self) -> None:
        if self._finished:
            msg = "request has already finished"
            raise RequestTracingError(msg)
        if self._active_stage is not None:
            msg = "cannot finish while a stage is active"
            raise RequestTracingError(msg)

    def _record_finished(self, trace: RequestTrace) -> RequestTrace:
        self._recorder.record(trace)
        self._finished = True
        return trace

    def _request_duration_ms(self) -> float:
        return self._elapsed_ms(
            self._start_monotonic, float(self._monotonic_clock.now())
        )

    def _elapsed_ms(self, start: float, end: float) -> float:
        if end < start:
            msg = "monotonic clock moved backwards"
            raise RequestTracingError(msg)
        return float((end - start) * 1000.0)
