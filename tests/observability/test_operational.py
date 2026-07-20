import pytest

from loreforge.observability import (
    InMemoryOperationalMetricsRecorder,
    OperationalMetricsError,
)


def test_operational_metrics_snapshot_is_deterministic_and_serializable() -> None:
    recorder = InMemoryOperationalMetricsRecorder()

    recorder.increment(
        "http_request_total",
        labels={"route": "/health", "method": "GET", "status_category": "2xx"},
    )
    recorder.increment(
        "retrieval_candidate_total", labels={"stage": "vector"}, amount=2
    )
    recorder.observe_duration(
        "http_request_duration_ms",
        12.5,
        labels={"route": "/health", "method": "GET", "status_category": "2xx"},
    )
    recorder.observe_duration(
        "http_request_duration_ms",
        7.5,
        labels={"route": "/health", "method": "GET", "status_category": "2xx"},
    )

    assert recorder.snapshot().as_dict() == {
        "counters": [
            {
                "name": "http_request_total",
                "labels": {
                    "method": "GET",
                    "route": "/health",
                    "status_category": "2xx",
                },
                "value": 1,
            },
            {
                "name": "retrieval_candidate_total",
                "labels": {"stage": "vector"},
                "value": 2,
            },
        ],
        "durations": [
            {
                "name": "http_request_duration_ms",
                "labels": {
                    "method": "GET",
                    "route": "/health",
                    "status_category": "2xx",
                },
                "count": 2,
                "total_ms": 20.0,
                "max_ms": 12.5,
            }
        ],
    }


@pytest.mark.parametrize(
    ("name", "labels", "amount"),
    [
        ("", None, 1),
        ("metric", {"route": ""}, 1),
        ("metric", {"user_id": "x" * 81}, 1),
        ("metric", None, 0),
    ],
)
def test_counter_validation_rejects_unsafe_metric_input(
    name: str,
    labels: dict[str, str] | None,
    amount: int,
) -> None:
    recorder = InMemoryOperationalMetricsRecorder()

    with pytest.raises(OperationalMetricsError):
        recorder.increment(name, labels=labels, amount=amount)


@pytest.mark.parametrize("duration", [-1.0, float("nan"), 1])
def test_duration_validation_rejects_invalid_values(duration: object) -> None:
    recorder = InMemoryOperationalMetricsRecorder()

    with pytest.raises(OperationalMetricsError):
        recorder.observe_duration("latency_ms", duration)  # type: ignore[arg-type]
