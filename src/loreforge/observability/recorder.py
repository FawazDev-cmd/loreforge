"""Metrics recorder protocol and in-memory implementation."""

from typing import Protocol, runtime_checkable
from uuid import UUID

from loreforge.observability.models import RequestTrace


class MetricsRecorderError(ValueError):
    """Raised when metrics recorder state would become invalid."""


@runtime_checkable
class MetricsRecorder(Protocol):
    """Recorder for completed request traces."""

    def record(self, trace: RequestTrace) -> None:
        """Record one completed request trace."""
        ...


class InMemoryMetricsRecorder:
    """Deterministic in-memory metrics recorder."""

    def __init__(self) -> None:
        self._traces: list[RequestTrace] = []
        self._request_ids: set[UUID] = set()

    def record(self, trace: RequestTrace) -> None:
        if trace.request_id in self._request_ids:
            msg = "request_id has already been recorded"
            raise MetricsRecorderError(msg)
        self._traces.append(trace)
        self._request_ids.add(trace.request_id)

    def snapshot(self) -> tuple[RequestTrace, ...]:
        return tuple(self._traces)

    def filter(
        self,
        *,
        operation: str | None = None,
        success: bool | None = None,
    ) -> tuple[RequestTrace, ...]:
        if operation is not None and not operation.strip():
            msg = "operation must not be empty when provided"
            raise ValueError(msg)
        if success is not None:
            success_object: object = success
            if type(success_object) is not bool:
                msg = "success must be a boolean when provided"
                raise ValueError(msg)
        return tuple(
            trace
            for trace in self._traces
            if (operation is None or trace.operation == operation)
            and (success is None or trace.success == success)
        )
