"""Latency summary helpers."""

from math import ceil

from loreforge.observability.models import LatencySummary, RequestTrace
from loreforge.observability.recorder import InMemoryMetricsRecorder


def summarize_latencies(traces: tuple[RequestTrace, ...]) -> LatencySummary:
    """Summarize request latencies with nearest-rank percentiles."""
    if not traces:
        msg = "traces must contain at least one trace"
        raise ValueError(msg)
    values = tuple(float(trace.duration_ms) for trace in traces)
    sorted_values = tuple(sorted(values))
    return LatencySummary(
        count=len(values),
        minimum_ms=float(sorted_values[0]),
        maximum_ms=float(sorted_values[-1]),
        mean_ms=float(sum(values) / len(values)),
        p50_ms=_nearest_rank(sorted_values, 0.50),
        p95_ms=_nearest_rank(sorted_values, 0.95),
    )


def summarize_operation(
    *,
    recorder: InMemoryMetricsRecorder,
    operation: str,
    success: bool | None = None,
) -> LatencySummary:
    """Summarize recorded traces for one operation and optional status."""
    traces = recorder.filter(operation=operation, success=success)
    if not traces:
        msg = "no traces match the requested operation"
        raise ValueError(msg)
    return summarize_latencies(traces)


def _nearest_rank(sorted_values: tuple[float, ...], percentile: float) -> float:
    rank = ceil(percentile * len(sorted_values))
    index = max(0, rank - 1)
    return float(sorted_values[index])
