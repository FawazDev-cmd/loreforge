"""Provider-neutral operational metrics for production diagnostics."""

from dataclasses import dataclass
from math import isfinite
from typing import Protocol, runtime_checkable

LabelSet = tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class CounterMetric:
    """Aggregated monotonically increasing counter."""

    name: str
    labels: LabelSet
    value: int


@dataclass(frozen=True, slots=True)
class DurationMetric:
    """Aggregated latency measurements in milliseconds."""

    name: str
    labels: LabelSet
    count: int
    total_ms: float
    max_ms: float


@dataclass(frozen=True, slots=True)
class OperationalMetricsSnapshot:
    """Immutable operational metrics snapshot."""

    counters: tuple[CounterMetric, ...]
    durations: tuple[DurationMetric, ...]

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable snapshot without high-cardinality labels."""
        return {
            "counters": [
                {
                    "name": metric.name,
                    "labels": dict(metric.labels),
                    "value": metric.value,
                }
                for metric in self.counters
            ],
            "durations": [
                {
                    "name": metric.name,
                    "labels": dict(metric.labels),
                    "count": metric.count,
                    "total_ms": metric.total_ms,
                    "max_ms": metric.max_ms,
                }
                for metric in self.durations
            ],
        }


class OperationalMetricsError(ValueError):
    """Raised when operational metric input is invalid."""


@runtime_checkable
class OperationalMetricsRecorder(Protocol):
    """Recorder for bounded operational counters and durations."""

    def increment(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
        amount: int = 1,
    ) -> None:
        """Increment one counter metric."""
        ...

    def observe_duration(
        self,
        name: str,
        duration_ms: float,
        *,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record one duration measurement in milliseconds."""
        ...

    def snapshot(self) -> OperationalMetricsSnapshot:
        """Return the current operational metric snapshot."""
        ...


class InMemoryOperationalMetricsRecorder:
    """Deterministic in-memory operational metrics recorder."""

    def __init__(self) -> None:
        self._counters: dict[tuple[str, LabelSet], int] = {}
        self._durations: dict[tuple[str, LabelSet], tuple[int, float, float]] = {}

    def increment(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
        amount: int = 1,
    ) -> None:
        if type(amount) is not int or amount <= 0:
            msg = "amount must be a positive integer"
            raise OperationalMetricsError(msg)
        key = (_validate_name(name), _labels(labels))
        self._counters[key] = self._counters.get(key, 0) + amount

    def observe_duration(
        self,
        name: str,
        duration_ms: float,
        *,
        labels: dict[str, str] | None = None,
    ) -> None:
        metric_name = _validate_name(name)
        value = _validate_duration(duration_ms)
        key = (metric_name, _labels(labels))
        count, total, maximum = self._durations.get(key, (0, 0.0, 0.0))
        self._durations[key] = (count + 1, total + value, max(maximum, value))

    def snapshot(self) -> OperationalMetricsSnapshot:
        counters = tuple(
            CounterMetric(name=name, labels=labels, value=value)
            for (name, labels), value in sorted(self._counters.items())
        )
        durations = tuple(
            DurationMetric(
                name=name,
                labels=labels,
                count=count,
                total_ms=total,
                max_ms=maximum,
            )
            for (name, labels), (count, total, maximum) in sorted(
                self._durations.items()
            )
        )
        return OperationalMetricsSnapshot(counters=counters, durations=durations)


def _validate_name(name: str) -> str:
    if not name.strip():
        msg = "metric name must not be empty"
        raise OperationalMetricsError(msg)
    return name


def _validate_duration(value: float) -> float:
    value_object: object = value
    if type(value_object) is not float or not isfinite(value) or value < 0.0:
        msg = "duration_ms must be a finite nonnegative float"
        raise OperationalMetricsError(msg)
    return value


def _labels(labels: dict[str, str] | None) -> LabelSet:
    if not labels:
        return ()
    normalized: list[tuple[str, str]] = []
    for key, value in labels.items():
        if not key.strip() or not value.strip():
            msg = "metric labels must not be empty"
            raise OperationalMetricsError(msg)
        if len(value) > 80:
            msg = "metric labels must be low-cardinality"
            raise OperationalMetricsError(msg)
        normalized.append((key, value))
    return tuple(sorted(normalized))
