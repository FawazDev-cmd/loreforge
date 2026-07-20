"""Regression threshold contracts and gate evaluation."""

from dataclasses import dataclass
from json import loads
from math import isfinite
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class EvaluationThresholds:
    """Version-controlled quality thresholds for deterministic regression gates."""

    min_hit_rate_at_k: float = 1.0
    min_recall_at_k: float = 1.0
    min_mrr: float = 1.0
    min_ndcg_at_k: float = 0.0
    min_citation_validity: float = 1.0
    min_citation_coverage: float = 1.0
    min_required_fact_coverage: float = 1.0
    min_abstention_correctness: float = 1.0
    max_error_count: int = 0

    def __post_init__(self) -> None:
        for name in (
            "min_hit_rate_at_k",
            "min_recall_at_k",
            "min_mrr",
            "min_ndcg_at_k",
            "min_citation_validity",
            "min_citation_coverage",
            "min_required_fact_coverage",
            "min_abstention_correctness",
        ):
            _validate_metric(getattr(self, name), name)
        max_error_count_object: object = self.max_error_count
        if type(max_error_count_object) is not int or self.max_error_count < 0:
            msg = "max_error_count must be a nonnegative integer"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class GateResult:
    """Regression gate outcome and failed threshold names."""

    passed: bool
    failed_thresholds: tuple[str, ...]


def load_thresholds(path: Path | str) -> EvaluationThresholds:
    """Load thresholds from a JSON file."""
    payload = loads(Path(path).read_text(encoding="utf-8"))
    if type(payload) is not dict:
        msg = "threshold JSON root must be an object"
        raise ValueError(msg)
    return thresholds_from_dict(payload)


def thresholds_from_dict(payload: dict[str, Any]) -> EvaluationThresholds:
    """Build validated thresholds from parsed JSON-compatible data."""
    return EvaluationThresholds(
        min_hit_rate_at_k=_float(payload, "min_hit_rate_at_k", 1.0),
        min_recall_at_k=_float(payload, "min_recall_at_k", 1.0),
        min_mrr=_float(payload, "min_mrr", 1.0),
        min_ndcg_at_k=_float(payload, "min_ndcg_at_k", 0.0),
        min_citation_validity=_float(payload, "min_citation_validity", 1.0),
        min_citation_coverage=_float(payload, "min_citation_coverage", 1.0),
        min_required_fact_coverage=_float(
            payload,
            "min_required_fact_coverage",
            1.0,
        ),
        min_abstention_correctness=_float(
            payload,
            "min_abstention_correctness",
            1.0,
        ),
        max_error_count=_int(payload, "max_error_count", 0),
    )


def evaluate_gate(
    *, aggregates: dict[str, float], thresholds: EvaluationThresholds
) -> GateResult:
    """Compare aggregate metrics to configured thresholds."""
    failures: list[str] = []
    _min(failures, aggregates, "mean_hit_rate_at_k", thresholds.min_hit_rate_at_k)
    _min(failures, aggregates, "mean_recall_at_k", thresholds.min_recall_at_k)
    _min(failures, aggregates, "mean_mrr", thresholds.min_mrr)
    _min(failures, aggregates, "mean_ndcg_at_k", thresholds.min_ndcg_at_k)
    _min(
        failures,
        aggregates,
        "mean_citation_validity",
        thresholds.min_citation_validity,
    )
    _min(
        failures,
        aggregates,
        "mean_citation_coverage",
        thresholds.min_citation_coverage,
    )
    _min(
        failures,
        aggregates,
        "mean_required_fact_coverage",
        thresholds.min_required_fact_coverage,
    )
    _min(
        failures,
        aggregates,
        "mean_abstention_correctness",
        thresholds.min_abstention_correctness,
    )
    if int(aggregates.get("error_count", 0.0)) > thresholds.max_error_count:
        failures.append("max_error_count")
    return GateResult(passed=not failures, failed_thresholds=tuple(failures))


def thresholds_as_dict(thresholds: EvaluationThresholds) -> dict[str, float | int]:
    """Serialize thresholds for reports."""
    return {
        "min_hit_rate_at_k": thresholds.min_hit_rate_at_k,
        "min_recall_at_k": thresholds.min_recall_at_k,
        "min_mrr": thresholds.min_mrr,
        "min_ndcg_at_k": thresholds.min_ndcg_at_k,
        "min_citation_validity": thresholds.min_citation_validity,
        "min_citation_coverage": thresholds.min_citation_coverage,
        "min_required_fact_coverage": thresholds.min_required_fact_coverage,
        "min_abstention_correctness": thresholds.min_abstention_correctness,
        "max_error_count": thresholds.max_error_count,
    }


def _min(
    failures: list[str],
    aggregates: dict[str, float],
    name: str,
    threshold: float,
) -> None:
    if aggregates.get(name, 0.0) < threshold:
        failures.append(name)


def _float(payload: dict[str, Any], key: str, default: float) -> float:
    value = payload.get(key, default)
    value_object: object = value
    if type(value_object) not in (float, int):
        msg = f"{key} must be a number"
        raise ValueError(msg)
    return float(value)


def _int(payload: dict[str, Any], key: str, default: int) -> int:
    value_object: object = payload.get(key, default)
    if type(value_object) is not int:
        msg = f"{key} must be an integer"
        raise ValueError(msg)
    return value_object


def _validate_metric(value: float, name: str) -> None:
    value_object: object = value
    if (
        type(value_object) is not float
        or not isfinite(value)
        or not 0.0 <= value <= 1.0
    ):
        msg = f"{name} must be between 0.0 and 1.0"
        raise ValueError(msg)
