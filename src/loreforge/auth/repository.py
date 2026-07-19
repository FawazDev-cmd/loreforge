"""Authentication repository protocols and in-memory adapters."""

from hmac import compare_digest
from typing import Protocol, runtime_checkable
from uuid import UUID

from loreforge.auth.models import UserIdentity


class AuthRepositoryError(ValueError):
    """Raised when authentication repository state would become invalid."""


@runtime_checkable
class UserRepository(Protocol):
    """Repository for durable user identity records."""

    def add(self, user: UserIdentity) -> None:
        """Add one user identity."""
        ...

    def get(self, user_id: UUID) -> UserIdentity | None:
        """Return a user identity when present."""
        ...

    def list(self) -> tuple[UserIdentity, ...]:
        """Return users in insertion order."""
        ...


@runtime_checkable
class ApiKeyRepository(Protocol):
    """Repository that resolves an API-key hash to a user identity."""

    def resolve(self, candidate_key_hash: str) -> UserIdentity | None:
        """Return the user for a safely hashed candidate key when present."""
        ...


class InMemoryUserRepository:
    """Deterministic in-memory user repository."""

    def __init__(self) -> None:
        self._users: dict[UUID, UserIdentity] = {}

    def add(self, user: UserIdentity) -> None:
        if user.user_id in self._users:
            msg = "user_id already exists"
            raise AuthRepositoryError(msg)
        self._users[user.user_id] = user

    def get(self, user_id: UUID) -> UserIdentity | None:
        return self._users.get(user_id)

    def list(self) -> tuple[UserIdentity, ...]:
        return tuple(self._users.values())


class InMemoryApiKeyRepository:
    """In-memory API-key repository storing only key hashes."""

    def __init__(
        self,
        credentials: tuple[tuple[str, UserIdentity], ...] = (),
    ) -> None:
        self._credentials = credentials

    def resolve(self, candidate_key_hash: str) -> UserIdentity | None:
        for key_hash, user in self._credentials:
            if compare_digest(key_hash, candidate_key_hash):
                return user
        return None
