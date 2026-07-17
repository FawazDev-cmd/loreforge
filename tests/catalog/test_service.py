from datetime import datetime, timezone
from uuid import UUID

import pytest

from loreforge.catalog import (
    CatalogEntry,
    CatalogService,
    CatalogServiceError,
    DocumentStatus,
    InMemoryCatalogRepository,
)

DOC1 = UUID("00000000-0000-0000-0000-000000000001")
DOC2 = UUID("00000000-0000-0000-0000-000000000002")
UPLOADED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_register_upload_creates_uploaded_entry() -> None:
    service = CatalogService(InMemoryCatalogRepository())

    entry = service.register_upload(
        document_id=DOC1,
        filename="policy.pdf",
        uploaded_at=UPLOADED_AT,
        page_count=4,
    )

    assert entry == CatalogEntry(
        document_id=DOC1,
        filename="policy.pdf",
        uploaded_at=UPLOADED_AT,
        page_count=4,
        chunk_count=0,
        status=DocumentStatus.UPLOADED,
    )
    assert service.get(DOC1) == entry


def test_valid_ready_lifecycle() -> None:
    service = CatalogService(InMemoryCatalogRepository())
    uploaded = service.register_upload(
        document_id=DOC1,
        filename="policy.pdf",
        uploaded_at=UPLOADED_AT,
    )

    ingesting = service.mark_ingesting(DOC1)
    ready = service.mark_ready(DOC1, page_count=8, chunk_count=12)
    deleted = service.mark_deleted(DOC1)

    assert uploaded.status is DocumentStatus.UPLOADED
    assert ingesting.status is DocumentStatus.INGESTING
    assert ready.status is DocumentStatus.READY
    assert ready.page_count == 8
    assert ready.chunk_count == 12
    assert deleted.status is DocumentStatus.DELETED


def test_valid_failed_lifecycle_from_uploaded() -> None:
    service = _service_with_upload()

    failed = service.mark_failed(DOC1)
    deleted = service.mark_deleted(DOC1)

    assert failed.status is DocumentStatus.FAILED
    assert deleted.status is DocumentStatus.DELETED


def test_valid_failed_lifecycle_from_ingesting() -> None:
    service = _service_with_upload()

    service.mark_ingesting(DOC1)
    failed = service.mark_failed(DOC1)

    assert failed.status is DocumentStatus.FAILED


@pytest.mark.parametrize(
    ("start_status", "operation"),
    [
        (DocumentStatus.UPLOADED, "ready"),
        (DocumentStatus.UPLOADED, "deleted"),
        (DocumentStatus.INGESTING, "deleted"),
        (DocumentStatus.READY, "ingesting"),
        (DocumentStatus.READY, "failed"),
        (DocumentStatus.FAILED, "ingesting"),
        (DocumentStatus.FAILED, "ready"),
        (DocumentStatus.DELETED, "ingesting"),
        (DocumentStatus.DELETED, "ready"),
        (DocumentStatus.DELETED, "failed"),
        (DocumentStatus.DELETED, "deleted"),
    ],
)
def test_invalid_lifecycle_transitions_rejected(
    start_status: DocumentStatus,
    operation: str,
) -> None:
    service = _service_with_status(start_status)

    with pytest.raises(CatalogServiceError, match="transition"):
        _apply_operation(service, operation)


def test_invalid_transition_leaves_entry_unchanged() -> None:
    service = _service_with_status(DocumentStatus.READY)
    before = service.get(DOC1)

    with pytest.raises(CatalogServiceError):
        service.mark_failed(DOC1)

    assert service.get(DOC1) == before


def test_mark_ready_validates_counts() -> None:
    service = _service_with_upload()
    service.mark_ingesting(DOC1)

    with pytest.raises(ValueError, match="chunk_count"):
        service.mark_ready(DOC1, page_count=1, chunk_count=-1)


def test_missing_document_rejected() -> None:
    service = CatalogService(InMemoryCatalogRepository())

    with pytest.raises(CatalogServiceError, match="document_id"):
        service.mark_ingesting(DOC1)


def test_service_list_uses_repository_order() -> None:
    service = CatalogService(InMemoryCatalogRepository())
    first = service.register_upload(
        document_id=DOC1,
        filename="policy.pdf",
        uploaded_at=UPLOADED_AT,
    )
    second = service.register_upload(
        document_id=DOC2,
        filename="handbook.pdf",
        uploaded_at=UPLOADED_AT,
    )

    assert service.list() == (first, second)


def test_service_rejects_duplicate_register_upload() -> None:
    service = _service_with_upload()

    with pytest.raises(ValueError, match="document_id"):
        service.register_upload(
            document_id=DOC1,
            filename="other.pdf",
            uploaded_at=UPLOADED_AT,
        )


def test_service_replaces_entries_without_mutating_previous_instance() -> None:
    service = _service_with_upload()
    uploaded = service.get(DOC1)

    ingesting = service.mark_ingesting(DOC1)

    assert uploaded is not None
    assert uploaded.status is DocumentStatus.UPLOADED
    assert ingesting.status is DocumentStatus.INGESTING
    assert ingesting is not uploaded


def test_deterministic_behavior_for_same_inputs() -> None:
    first = _run_ready_lifecycle()
    second = _run_ready_lifecycle()

    assert first == second


def _service_with_upload() -> CatalogService:
    service = CatalogService(InMemoryCatalogRepository())
    service.register_upload(
        document_id=DOC1,
        filename="policy.pdf",
        uploaded_at=UPLOADED_AT,
    )
    return service


def _service_with_status(status: DocumentStatus) -> CatalogService:
    service = _service_with_upload()
    if status is DocumentStatus.UPLOADED:
        return service
    if status is DocumentStatus.INGESTING:
        service.mark_ingesting(DOC1)
        return service
    if status is DocumentStatus.READY:
        service.mark_ingesting(DOC1)
        service.mark_ready(DOC1, page_count=1, chunk_count=1)
        return service
    if status is DocumentStatus.FAILED:
        service.mark_failed(DOC1)
        return service
    service.mark_failed(DOC1)
    service.mark_deleted(DOC1)
    return service


def _apply_operation(service: CatalogService, operation: str) -> None:
    if operation == "ingesting":
        service.mark_ingesting(DOC1)
    elif operation == "ready":
        service.mark_ready(DOC1, page_count=1, chunk_count=1)
    elif operation == "failed":
        service.mark_failed(DOC1)
    elif operation == "deleted":
        service.mark_deleted(DOC1)


def _run_ready_lifecycle() -> tuple[CatalogEntry, ...]:
    service = _service_with_upload()
    service.mark_ingesting(DOC1)
    service.mark_ready(DOC1, page_count=1, chunk_count=1)
    return service.list()
