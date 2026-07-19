"""Framework-independent authentication domain models."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserIdentity:
    """Stable LoreForge user identity."""

    user_id: UUID
    display_name: str | None = None

    def __post_init__(self) -> None:
        if type(self.user_id) is not UUID:
            msg = "user_id must be a UUID"
            raise ValueError(msg)
        if self.display_name is not None and not self.display_name.strip():
            msg = "display_name must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Authenticated request identity passed into application boundaries."""

    user: UserIdentity

    def __post_init__(self) -> None:
        if type(self.user) is not UserIdentity:
            msg = "user must be a UserIdentity"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class DocumentOwnership:
    """Ownership link between a user and a persisted document."""

    document_id: UUID
    owner_user_id: UUID

    def __post_init__(self) -> None:
        if type(self.document_id) is not UUID:
            msg = "document_id must be a UUID"
            raise ValueError(msg)
        if type(self.owner_user_id) is not UUID:
            msg = "owner_user_id must be a UUID"
            raise ValueError(msg)
