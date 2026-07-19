"""Indexing-state metadata models and repositories."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID


class IndexingStatus(StrEnum):
    """Durable indexing lifecycle status."""

    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class IndexingState:
    """Immutable metadata snapshot for one indexing attempt."""

    state_id: UUID
    document_id: UUID
    status: IndexingStatus
    started_at: datetime
    updated_at: datetime
    page_count: int = 0
    chunk_count: int = 0
    completed_at: datetime | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.state_id, "state_id")
        _require_uuid(self.document_id, "document_id")
        if type(self.status) is not IndexingStatus:
            msg = "status must be an IndexingStatus"
            raise ValueError(msg)
        _require_utc(self.started_at, "started_at")
        _require_utc(self.updated_at, "updated_at")
        if self.completed_at is not None:
            _require_utc(self.completed_at, "completed_at")
        _validate_nonnegative_int(self.page_count, "page_count")
        _validate_nonnegative_int(self.chunk_count, "chunk_count")
        if self.error_message is not None and not self.error_message.strip():
            msg = "error_message must not be empty when provided"
            raise ValueError(msg)


class IndexingStateRepositoryError(ValueError):
    """Raised when indexing-state repository data would become invalid."""


@runtime_checkable
class IndexingStateRepository(Protocol):
    """Repository for indexing-state metadata snapshots."""

    def add(self, state: IndexingState) -> None:
        """Add one indexing-state snapshot."""
        ...

    def get(self, state_id: UUID) -> IndexingState | None:
        """Return an indexing-state snapshot by ID when present."""
        ...

    def list(self) -> tuple[IndexingState, ...]:
        """Return indexing-state snapshots in insertion order."""
        ...

    def list_for_document(self, document_id: UUID) -> tuple[IndexingState, ...]:
        """Return indexing-state snapshots for one document in insertion order."""
        ...

    def update(self, state: IndexingState) -> None:
        """Replace an existing indexing-state snapshot."""
        ...

    def remove(self, state_id: UUID) -> bool:
        """Remove an indexing-state snapshot by ID."""
        ...


class InMemoryIndexingStateRepository:
    """Deterministic in-memory indexing-state repository."""

    def __init__(self) -> None:
        self._states: dict[UUID, IndexingState] = {}

    def add(self, state: IndexingState) -> None:
        if state.state_id in self._states:
            msg = "state_id already exists in indexing state"
            raise IndexingStateRepositoryError(msg)
        self._states[state.state_id] = state

    def get(self, state_id: UUID) -> IndexingState | None:
        return self._states.get(state_id)

    def list(self) -> tuple[IndexingState, ...]:
        return tuple(self._states.values())

    def list_for_document(self, document_id: UUID) -> tuple[IndexingState, ...]:
        return tuple(
            state for state in self._states.values() if state.document_id == document_id
        )

    def update(self, state: IndexingState) -> None:
        if state.state_id not in self._states:
            msg = "state_id does not exist in indexing state"
            raise IndexingStateRepositoryError(msg)
        self._states[state.state_id] = state

    def remove(self, state_id: UUID) -> bool:
        if state_id not in self._states:
            return False
        del self._states[state_id]
        return True


def _require_uuid(value: UUID, name: str) -> None:
    if type(value) is not UUID:
        msg = f"{name} must be a UUID"
        raise ValueError(msg)


def _require_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        msg = f"{name} must be timezone-aware"
        raise ValueError(msg)
    if value.utcoffset() != timezone.utc.utcoffset(value):
        msg = f"{name} must be UTC"
        raise ValueError(msg)


def _validate_nonnegative_int(value: int, name: str) -> None:
    value_object: object = value
    if type(value_object) is not int:
        msg = f"{name} must be an integer"
        raise ValueError(msg)
    if value < 0:
        msg = f"{name} must be greater than or equal to zero"
        raise ValueError(msg)
