"""Immutable observability metric models."""

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RuntimeQueryObservation:
    """Safe runtime facts captured for one grounded query."""

    semantic_result_count: int | None = None
    lexical_result_count: int | None = None
    fused_result_count: int | None = None
    reranked_result_count: int | None = None
    evidence_count: int | None = None
    citation_count: int | None = None
    citations_valid: bool | None = None
    citation_precision: float | None = None
    citation_recall: float | None = None
    provider_model: str | None = None
    finish_reason: str | None = None
    failure_category: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("semantic_result_count", self.semantic_result_count),
            ("lexical_result_count", self.lexical_result_count),
            ("fused_result_count", self.fused_result_count),
            ("reranked_result_count", self.reranked_result_count),
            ("evidence_count", self.evidence_count),
            ("citation_count", self.citation_count),
        ):
            _validate_optional_nonnegative_int(value, name)

        _validate_optional_bool(self.citations_valid, "citations_valid")
        _validate_optional_metric(self.citation_precision, "citation_precision")
        _validate_optional_metric(self.citation_recall, "citation_recall")
        _validate_optional_string(self.provider_model, "provider_model")
        _validate_optional_string(self.finish_reason, "finish_reason")
        _validate_optional_string(self.failure_category, "failure_category")


@dataclass(frozen=True, slots=True)
class StageMetric:
    """Latency and status for one observed stage."""

    name: str
    duration_ms: float
    success: bool
    error_type: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            msg = "name must not be empty"
            raise ValueError(msg)
        _validate_nonnegative_float(self.duration_ms, "duration_ms")
        _validate_bool(self.success, "success")
        if self.success and self.error_type is not None:
            msg = "successful stages must not include error_type"
            raise ValueError(msg)
        if not self.success:
            if self.error_type is None or not self.error_type.strip():
                msg = "failed stages must include a nonblank error_type"
                raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RequestTrace:
    """Request-level trace with ordered stage metrics."""

    request_id: UUID
    operation: str
    started_at: datetime
    duration_ms: float
    success: bool
    stages: tuple[StageMetric, ...]
    error_type: str | None = None
    observation: RuntimeQueryObservation | None = None

    def __post_init__(self) -> None:
        if not self.operation.strip():
            msg = "operation must not be empty"
            raise ValueError(msg)
        if self.started_at.tzinfo is None or self.started_at.utcoffset() is None:
            msg = "started_at must be timezone-aware"
            raise ValueError(msg)
        if self.started_at.utcoffset() != timezone.utc.utcoffset(self.started_at):
            msg = "started_at must be UTC"
            raise ValueError(msg)
        _validate_nonnegative_float(self.duration_ms, "duration_ms")
        _validate_bool(self.success, "success")
        stage_names = tuple(stage.name for stage in self.stages)
        if len(set(stage_names)) != len(stage_names):
            msg = "stage names must be unique"
            raise ValueError(msg)
        if any(stage.duration_ms > self.duration_ms for stage in self.stages):
            msg = "duration_ms must be greater than or equal to stage durations"
            raise ValueError(msg)
        if self.success:
            if self.error_type is not None:
                msg = "successful traces must not include error_type"
                raise ValueError(msg)
            if any(not stage.success for stage in self.stages):
                msg = "successful traces must not contain failed stages"
                raise ValueError(msg)
        else:
            if self.error_type is not None and not self.error_type.strip():
                msg = "failed traces must include a nonblank error_type when provided"
                raise ValueError(msg)
            if self.error_type is None and not any(
                not stage.success for stage in self.stages
            ):
                msg = "failed traces must include a failed stage or error_type"
                raise ValueError(msg)
        if (
            self.observation is not None
            and type(self.observation) is not RuntimeQueryObservation
        ):
            msg = "observation must be a RuntimeQueryObservation when provided"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class LatencySummary:
    """Summary statistics for request latencies."""

    count: int
    minimum_ms: float
    maximum_ms: float
    mean_ms: float
    p50_ms: float
    p95_ms: float

    def __post_init__(self) -> None:
        count: object = self.count
        if type(count) is not int:
            msg = "count must be an integer"
            raise ValueError(msg)
        if self.count <= 0:
            msg = "count must be greater than zero"
            raise ValueError(msg)
        for name, value in (
            ("minimum_ms", self.minimum_ms),
            ("maximum_ms", self.maximum_ms),
            ("mean_ms", self.mean_ms),
            ("p50_ms", self.p50_ms),
            ("p95_ms", self.p95_ms),
        ):
            _validate_nonnegative_float(value, name)
        if not self.minimum_ms <= self.mean_ms <= self.maximum_ms:
            msg = "mean_ms must be between minimum_ms and maximum_ms"
            raise ValueError(msg)
        if not self.minimum_ms <= self.p50_ms <= self.maximum_ms:
            msg = "p50_ms must be between minimum_ms and maximum_ms"
            raise ValueError(msg)
        if not self.minimum_ms <= self.p95_ms <= self.maximum_ms:
            msg = "p95_ms must be between minimum_ms and maximum_ms"
            raise ValueError(msg)
        if self.p50_ms > self.p95_ms:
            msg = "p50_ms must be less than or equal to p95_ms"
            raise ValueError(msg)


def _validate_nonnegative_float(value: float, name: str) -> None:
    value_object: object = value
    if type(value_object) is not float:
        msg = f"{name} must be a float"
        raise ValueError(msg)
    if not isfinite(value):
        msg = f"{name} must be finite"
        raise ValueError(msg)
    if value < 0.0:
        msg = f"{name} must be greater than or equal to zero"
        raise ValueError(msg)


def _validate_bool(value: bool, name: str) -> None:
    value_object: object = value
    if type(value_object) is not bool:
        msg = f"{name} must be a boolean"
        raise ValueError(msg)


def _validate_optional_bool(value: bool | None, name: str) -> None:
    if value is None:
        return
    _validate_bool(value, name)


def _validate_optional_metric(value: float | None, name: str) -> None:
    if value is None:
        return
    _validate_metric(value, name)


def _validate_optional_nonnegative_int(value: int | None, name: str) -> None:
    if value is None:
        return
    value_object: object = value
    if type(value_object) is not int:
        msg = f"{name} must be an integer when provided"
        raise ValueError(msg)
    if value < 0:
        msg = f"{name} must be greater than or equal to zero when provided"
        raise ValueError(msg)


def _validate_metric(value: float, name: str) -> None:
    value_object: object = value
    if type(value_object) is not float:
        msg = f"{name} must be a float"
        raise ValueError(msg)
    if not isfinite(value):
        msg = f"{name} must be finite"
        raise ValueError(msg)
    if not 0.0 <= value <= 1.0:
        msg = f"{name} must be between 0.0 and 1.0"
        raise ValueError(msg)


def _validate_optional_string(value: str | None, name: str) -> None:
    if value is None:
        return
    if not value.strip():
        msg = f"{name} must not be empty when provided"
        raise ValueError(msg)
