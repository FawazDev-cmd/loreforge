from datetime import datetime, timezone
from uuid import UUID

import pytest

from loreforge.catalog import (
    CatalogEntry,
    CatalogRepository,
    CatalogRepositoryError,
    DocumentStatus,
    InMemoryCatalogRepository,
)

DOC1 = UUID("00000000-0000-0000-0000-000000000001")
DOC2 = UUID("00000000-0000-0000-0000-000000000002")
UPLOADED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_repository_satisfies_protocol() -> None:
    assert isinstance(InMemoryCatalogRepository(), CatalogRepository)


def test_empty_repository_initial_state() -> None:
    repository = InMemoryCatalogRepository()

    assert repository.get(DOC1) is None
    assert repository.list() == ()


def test_add_and_get_entry() -> None:
    repository = InMemoryCatalogRepository()
    entry = _entry(DOC1)

    repository.add(entry)

    assert repository.get(DOC1) == entry


def test_list_preserves_insertion_order() -> None:
    repository = _repository_with(_entry(DOC1), _entry(DOC2, filename="handbook.pdf"))

    assert [entry.document_id for entry in repository.list()] == [DOC1, DOC2]


def test_duplicate_insert_rejected() -> None:
    repository = InMemoryCatalogRepository()
    repository.add(_entry(DOC1))

    with pytest.raises(CatalogRepositoryError, match="document_id"):
        repository.add(_entry(DOC1, filename="other.pdf"))


def test_duplicate_insert_leaves_repository_unchanged() -> None:
    repository = InMemoryCatalogRepository()
    entry = _entry(DOC1)
    repository.add(entry)

    with pytest.raises(CatalogRepositoryError):
        repository.add(_entry(DOC1, filename="other.pdf"))

    assert repository.list() == (entry,)


def test_update_replaces_existing_entry() -> None:
    repository = _repository_with(_entry(DOC1))
    updated = _entry(DOC1, status=DocumentStatus.INGESTING)

    repository.update(updated)

    assert repository.get(DOC1) == updated


def test_update_preserves_insertion_order() -> None:
    first = _entry(DOC1)
    second = _entry(DOC2, filename="handbook.pdf")
    repository = _repository_with(first, second)

    repository.update(_entry(DOC1, status=DocumentStatus.FAILED))

    assert [entry.document_id for entry in repository.list()] == [DOC1, DOC2]


def test_update_missing_entry_rejected() -> None:
    repository = InMemoryCatalogRepository()

    with pytest.raises(CatalogRepositoryError, match="does not exist"):
        repository.update(_entry(DOC1))


def test_remove_existing_entry() -> None:
    repository = _repository_with(_entry(DOC1))

    assert repository.remove(DOC1) is True
    assert repository.get(DOC1) is None
    assert repository.list() == ()


def test_remove_missing_entry_returns_false() -> None:
    assert InMemoryCatalogRepository().remove(DOC1) is False


def test_snapshot_is_tuple() -> None:
    assert isinstance(InMemoryCatalogRepository().list(), tuple)


def test_snapshot_does_not_expose_internal_state() -> None:
    repository = _repository_with(_entry(DOC1))
    snapshot = repository.list()

    snapshot += (_entry(DOC2, filename="handbook.pdf"),)

    assert repository.list() == (_entry(DOC1),)


def test_repeated_lists_are_deterministic() -> None:
    repository = _repository_with(_entry(DOC1), _entry(DOC2, filename="handbook.pdf"))

    assert repository.list() == repository.list()


def _repository_with(*entries: CatalogEntry) -> InMemoryCatalogRepository:
    repository = InMemoryCatalogRepository()
    for entry in entries:
        repository.add(entry)
    return repository


def _entry(
    document_id: UUID,
    *,
    filename: str = "policy.pdf",
    status: DocumentStatus = DocumentStatus.UPLOADED,
) -> CatalogEntry:
    return CatalogEntry(
        document_id=document_id,
        filename=filename,
        uploaded_at=UPLOADED_AT,
        page_count=0,
        chunk_count=0,
        status=status,
    )
