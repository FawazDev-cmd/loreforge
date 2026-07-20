"""Request-local observability context."""

from contextvars import ContextVar, Token
from uuid import UUID

_request_id: ContextVar[UUID | None] = ContextVar("request_id", default=None)
_user_id: ContextVar[UUID | None] = ContextVar("user_id", default=None)


def current_request_id() -> UUID | None:
    """Return the request ID bound to the current context."""
    return _request_id.get()


def set_request_id(request_id: UUID) -> Token[UUID | None]:
    """Bind a request ID to the current context."""
    return _request_id.set(request_id)


def reset_request_id(token: Token[UUID | None]) -> None:
    """Reset the request ID context to a previous token."""
    _request_id.reset(token)


def current_user_id() -> UUID | None:
    """Return the authenticated user ID bound to the current context."""
    return _user_id.get()


def set_user_id(user_id: UUID | None) -> Token[UUID | None]:
    """Bind an authenticated user ID to the current context."""
    return _user_id.set(user_id)


def reset_user_id(token: Token[UUID | None]) -> None:
    """Reset the user ID context to a previous token."""
    _user_id.reset(token)
