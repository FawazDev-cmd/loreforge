from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from loreforge.catalog import CatalogEntry, DocumentStatus

DOC1 = UUID("00000000-0000-0000-0000-000000000001")
UPLOADED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_document_status_values() -> None:
    assert [status.value for status in DocumentStatus] == [
        "UPLOADED",
        "INGESTING",
        "READY",
        "FAILED",
        "DELETED",
    ]


def test_catalog_entry_valid_values() -> None:
    entry = _entry()

    assert entry.document_id == DOC1
    assert entry.filename == "policy.pdf"
    assert entry.uploaded_at == UPLOADED_AT
    assert entry.page_count == 2
    assert entry.chunk_count == 3
    assert entry.status is DocumentStatus.UPLOADED


@pytest.mark.parametrize("filename", ["", "   "])
def test_catalog_entry_blank_filename_rejected(filename: str) -> None:
    with pytest.raises(ValueError, match="filename"):
        _entry(filename=filename)


def test_catalog_entry_naive_timestamp_rejected() -> None:
    with pytest.raises(ValueError, match="timezone"):
        _entry(uploaded_at=datetime(2026, 1, 1))


def test_catalog_entry_non_utc_timestamp_rejected() -> None:
    with pytest.raises(ValueError, match="UTC"):
        _entry(uploaded_at=datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=1))))


@pytest.mark.parametrize("page_count", [-1, 1.5, True])
def test_catalog_entry_invalid_page_count_rejected(page_count: object) -> None:
    with pytest.raises(ValueError, match="page_count"):
        _entry(page_count=page_count)  # type: ignore[arg-type]


@pytest.mark.parametrize("chunk_count", [-1, 1.5, True])
def test_catalog_entry_invalid_chunk_count_rejected(chunk_count: object) -> None:
    with pytest.raises(ValueError, match="chunk_count"):
        _entry(chunk_count=chunk_count)  # type: ignore[arg-type]


def test_catalog_entry_is_immutable() -> None:
    entry = _entry()

    with pytest.raises(FrozenInstanceError):
        entry.status = DocumentStatus.READY


def test_catalog_entry_invalid_status_rejected() -> None:
    with pytest.raises(ValueError, match="status"):
        _entry(status="UPLOADED")  # type: ignore[arg-type]


def _entry(
    *,
    document_id: UUID = DOC1,
    filename: str = "policy.pdf",
    uploaded_at: datetime = UPLOADED_AT,
    page_count: int = 2,
    chunk_count: int = 3,
    status: DocumentStatus = DocumentStatus.UPLOADED,
) -> CatalogEntry:
    return CatalogEntry(
        document_id=document_id,
        filename=filename,
        uploaded_at=uploaded_at,
        page_count=page_count,
        chunk_count=chunk_count,
        status=status,
    )
