from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from uuid import UUID

import pytest

from loreforge.indexing import (
    IndexingState,
    IndexingStateRepository,
    IndexingStateRepositoryError,
    IndexingStatus,
    InMemoryIndexingStateRepository,
)

STATE1 = UUID("00000000-0000-0000-0000-000000000101")
STATE2 = UUID("00000000-0000-0000-0000-000000000102")
DOC1 = UUID("00000000-0000-0000-0000-000000000001")
DOC2 = UUID("00000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_indexing_state_is_immutable() -> None:
    state = _state(STATE1, DOC1)

    with pytest.raises(FrozenInstanceError):
        state.status = IndexingStatus.FAILED  # type: ignore[misc]


def test_indexing_state_requires_uuid_fields() -> None:
    with pytest.raises(ValueError, match="state_id"):
        IndexingState(  # type: ignore[arg-type]
            state_id="bad",
            document_id=DOC1,
            status=IndexingStatus.STARTED,
            started_at=NOW,
            updated_at=NOW,
        )


def test_indexing_state_requires_utc_datetimes() -> None:
    with pytest.raises(ValueError, match="started_at"):
        IndexingState(
            state_id=STATE1,
            document_id=DOC1,
            status=IndexingStatus.STARTED,
            started_at=datetime(2026, 1, 1),
            updated_at=NOW,
        )


def test_indexing_state_rejects_invalid_counts() -> None:
    with pytest.raises(ValueError, match="chunk_count"):
        _state(STATE1, DOC1, chunk_count=-1)


def test_indexing_state_rejects_blank_error_message() -> None:
    with pytest.raises(ValueError, match="error_message"):
        _state(STATE1, DOC1, status=IndexingStatus.FAILED, error_message="   ")


def test_in_memory_indexing_state_repository_satisfies_protocol() -> None:
    assert isinstance(InMemoryIndexingStateRepository(), IndexingStateRepository)


def test_in_memory_indexing_state_repository_crud_and_ordering() -> None:
    repository = InMemoryIndexingStateRepository()
    first = _state(STATE1, DOC1)
    second = _state(STATE2, DOC2)

    repository.add(first)
    repository.add(second)

    assert repository.get(STATE1) == first
    assert repository.list() == (first, second)
    assert repository.list_for_document(DOC1) == (first,)

    updated = _state(STATE1, DOC1, status=IndexingStatus.FAILED)
    repository.update(updated)

    assert repository.list() == (updated, second)
    assert repository.remove(STATE1) is True
    assert repository.remove(STATE1) is False
    assert repository.list() == (second,)


def test_in_memory_indexing_state_repository_rejects_duplicates() -> None:
    repository = InMemoryIndexingStateRepository()
    repository.add(_state(STATE1, DOC1))

    with pytest.raises(IndexingStateRepositoryError, match="state_id"):
        repository.add(_state(STATE1, DOC1))


def test_in_memory_indexing_state_repository_rejects_missing_update() -> None:
    repository = InMemoryIndexingStateRepository()

    with pytest.raises(IndexingStateRepositoryError, match="does not exist"):
        repository.update(_state(STATE1, DOC1))


def _state(
    state_id: UUID,
    document_id: UUID,
    *,
    status: IndexingStatus = IndexingStatus.STARTED,
    chunk_count: int = 0,
    error_message: str | None = None,
) -> IndexingState:
    return IndexingState(
        state_id=state_id,
        document_id=document_id,
        status=status,
        started_at=NOW,
        updated_at=NOW,
        chunk_count=chunk_count,
        error_message=error_message,
    )
