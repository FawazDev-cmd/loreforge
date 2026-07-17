from datetime import timezone

from loreforge.observability import (
    MonotonicClock,
    SystemMonotonicClock,
    SystemUtcClock,
    UtcClock,
)


class Incompatible:
    pass


def test_system_monotonic_clock_satisfies_protocol() -> None:
    assert isinstance(SystemMonotonicClock(), MonotonicClock)
    assert isinstance(SystemMonotonicClock().now(), float)


def test_system_utc_clock_satisfies_protocol() -> None:
    assert isinstance(SystemUtcClock(), UtcClock)


def test_system_utc_clock_returns_timezone_aware_utc() -> None:
    now = SystemUtcClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timezone.utc.utcoffset(now)


def test_incompatible_objects_fail_protocol_checks() -> None:
    assert not isinstance(Incompatible(), MonotonicClock)
    assert not isinstance(Incompatible(), UtcClock)
