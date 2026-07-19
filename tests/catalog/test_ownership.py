from datetime import datetime, timezone
from uuid import UUID

import pytest

from loreforge.catalog import (
    CatalogService,
    CatalogServiceError,
    InMemoryCatalogRepository,
)

DOC1 = UUID("00000000-0000-0000-0000-000000000001")
USER1 = UUID("00000000-0000-0000-0000-000000000111")
USER2 = UUID("00000000-0000-0000-0000-000000000222")
UPLOADED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_catalog_owner_scoped_access_and_listing() -> None:
    service = CatalogService(InMemoryCatalogRepository())
    entry = service.register_upload(
        document_id=DOC1,
        filename="policy.pdf",
        uploaded_at=UPLOADED_AT,
        owner_user_id=USER1,
    )

    assert entry.owner_user_id == USER1
    assert service.get_for_owner(DOC1, USER1) == entry
    assert service.get_for_owner(DOC1, USER2) is None
    assert service.list_for_owner(USER1) == (entry,)
    assert service.list_for_owner(USER2) == ()


def test_catalog_owner_scoped_lifecycle_rejects_cross_owner() -> None:
    service = CatalogService(InMemoryCatalogRepository())
    service.register_upload(
        document_id=DOC1,
        filename="policy.pdf",
        uploaded_at=UPLOADED_AT,
        owner_user_id=USER1,
    )

    with pytest.raises(CatalogServiceError, match="does not exist"):
        service.mark_ingesting_for_owner(DOC1, USER2)

    ingesting = service.mark_ingesting_for_owner(DOC1, USER1)
    ready = service.mark_ready_for_owner(
        DOC1,
        USER1,
        page_count=2,
        chunk_count=3,
    )

    assert ingesting.status == "INGESTING"
    assert ready.owner_user_id == USER1
