"""Clock protocols and system clock implementations."""

from datetime import datetime, timezone
from time import perf_counter
from typing import Protocol, runtime_checkable


@runtime_checkable
class MonotonicClock(Protocol):
    """Clock that returns monotonic seconds."""

    def now(self) -> float:
        """Return monotonic seconds."""
        ...


@runtime_checkable
class UtcClock(Protocol):
    """Clock that returns timezone-aware UTC datetimes."""

    def now(self) -> datetime:
        """Return the current UTC datetime."""
        ...


class SystemMonotonicClock:
    """System monotonic clock backed by perf_counter."""

    def now(self) -> float:
        return float(perf_counter())


class SystemUtcClock:
    """System UTC wall clock."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
