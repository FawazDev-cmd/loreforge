"""Demo-access policy helpers for HTTP presentation routes."""

from collections import deque
from collections.abc import Callable
from time import perf_counter
from uuid import UUID

from fastapi import HTTPException, Request, status

from loreforge.application import ApplicationContainer
from loreforge.auth import AuthenticatedPrincipal

_DEMO_FORBIDDEN_DETAIL = "demo access is read-only"
_DEMO_RATE_LIMIT_DETAIL = "demo ask rate limit exceeded"


class InMemoryDemoRateLimiter:
    """Small single-process sliding-window limiter for demo identities."""

    def __init__(self, clock: Callable[[], float] = perf_counter) -> None:
        self._clock = clock
        self._requests: dict[UUID, deque[float]] = {}

    def allow(self, user_id: UUID, *, max_requests: int, window_seconds: int) -> bool:
        """Return whether a demo user may start another expensive request."""
        now = self._clock()
        timestamps = self._requests.setdefault(user_id, deque())
        while timestamps and now - timestamps[0] >= float(window_seconds):
            timestamps.popleft()
        if len(timestamps) >= max_requests:
            return False
        timestamps.append(now)
        return True


def is_demo_principal(principal: AuthenticatedPrincipal | None) -> bool:
    """Return whether the authenticated principal is configured as demo access."""
    return principal is not None and principal.user.is_demo


def require_not_demo(principal: AuthenticatedPrincipal | None) -> None:
    """Reject protected mutations for demo access identities."""
    if is_demo_principal(principal):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_DEMO_FORBIDDEN_DETAIL,
        )


def enforce_demo_ask_rate_limit(
    request: Request,
    principal: AuthenticatedPrincipal | None,
) -> None:
    """Apply the configured demo-only AskMe rate limit."""
    if not is_demo_principal(principal):
        return
    assert principal is not None

    container = getattr(request.app.state, "container", None)
    limiter = getattr(request.app.state, "demo_rate_limiter", None)
    if (
        type(container) is not ApplicationContainer
        or type(limiter) is not InMemoryDemoRateLimiter
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Application services are unavailable.",
        )

    if not limiter.allow(
        principal.user.user_id,
        max_requests=container.settings.auth.demo_ask_rate_limit_requests,
        window_seconds=container.settings.auth.demo_ask_rate_limit_window_seconds,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_DEMO_RATE_LIMIT_DETAIL,
        )
