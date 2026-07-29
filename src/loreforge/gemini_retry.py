"""Internal retry helpers for transient Gemini SDK failures."""

from __future__ import annotations

import logging
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from time import sleep
from typing import TypeVar

_logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 0.5
_MAX_DELAY_SECONDS = 2.0
_JITTER_FRACTION = 0.25
_TRANSIENT_STATUS_CODES = frozenset({429, 503})
_PERMANENT_STATUS_CODES = frozenset({400, 401, 403})

T = TypeVar("T")
SleepFunction = Callable[[float], None]
JitterFunction = Callable[[float], float]


@dataclass(slots=True)
class GeminiRetryPolicy:
    """Bounded exponential retry policy for transient Gemini API failures."""

    sleep: SleepFunction = sleep
    jitter: JitterFunction = field(default_factory=lambda: _default_jitter)
    max_attempts: int = _MAX_ATTEMPTS

    def __post_init__(self) -> None:
        if self.max_attempts <= 0:
            msg = "max_attempts must be positive"
            raise ValueError(msg)


def call_with_gemini_retries(
    operation: Callable[[], T],
    *,
    operation_name: str,
    policy: GeminiRetryPolicy,
) -> T:
    """Call a Gemini SDK operation with bounded retries for transient failures."""
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return operation()
        except Exception as error:
            reason = _failure_reason(error)
            should_retry = _is_transient_failure(error)
            attempts_exhausted = attempt >= policy.max_attempts
            if not should_retry:
                raise
            if attempts_exhausted:
                _logger.warning(
                    "gemini.retry.exhausted operation=%s attempt=%d reason=%s",
                    operation_name,
                    attempt,
                    reason,
                )
                raise

            delay_seconds = _retry_delay_seconds(attempt, policy.jitter)
            _logger.warning(
                "gemini.retry.scheduled operation=%s attempt=%d next_attempt=%d "
                "reason=%s delay_seconds=%.3f",
                operation_name,
                attempt,
                attempt + 1,
                reason,
                delay_seconds,
            )
            policy.sleep(delay_seconds)

    raise RuntimeError("unreachable Gemini retry state")


def _retry_delay_seconds(attempt: int, jitter: JitterFunction) -> float:
    base_delay: float = min(
        _MAX_DELAY_SECONDS, _BASE_DELAY_SECONDS * (2 ** (attempt - 1))
    )
    raw_jitter: float = float(jitter(base_delay))
    bounded_jitter: float = max(0.0, min(base_delay * _JITTER_FRACTION, raw_jitter))
    return float(base_delay + bounded_jitter)


def _default_jitter(base_delay: float) -> float:
    return random.uniform(0.0, base_delay * _JITTER_FRACTION)


def _is_transient_failure(error: Exception) -> bool:
    status_code = _status_code(error)
    if status_code in _PERMANENT_STATUS_CODES:
        return False
    if status_code in _TRANSIENT_STATUS_CODES:
        return True
    if _is_timeout_error(error):
        return True
    if _is_temporary_transport_error(error):
        return True
    return False


def _failure_reason(error: Exception) -> str:
    status_code = _status_code(error)
    if status_code is not None:
        return f"http_{status_code}"
    if _is_timeout_error(error):
        return "timeout"
    if _is_temporary_transport_error(error):
        return "transport"
    return type(error).__name__


def _status_code(error: Exception) -> int | None:
    for name in ("status_code", "status", "code"):
        value = getattr(error, name, None)
        status_code = _coerce_status_code(value)
        if status_code is not None:
            return status_code
    response = getattr(error, "response", None)
    if response is not None:
        return _coerce_status_code(getattr(response, "status_code", None))
    return None


def _coerce_status_code(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _is_timeout_error(error: Exception) -> bool:
    if isinstance(error, TimeoutError):
        return True
    return "timeout" in type(error).__name__.lower()


def _is_temporary_transport_error(error: Exception) -> bool:
    if isinstance(error, ConnectionError):
        return True
    name = type(error).__name__.lower()
    return any(
        marker in name
        for marker in (
            "connectionerror",
            "connecterror",
            "networkerror",
            "readerror",
            "remoteprotocolerror",
            "transporterror",
        )
    )


__all__ = ["GeminiRetryPolicy", "call_with_gemini_retries"]
