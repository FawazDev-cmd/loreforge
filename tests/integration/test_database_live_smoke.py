import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from loreforge.catalog import CatalogEntry, DocumentStatus
from loreforge.database import (
    SqlAlchemyCatalogRepository,
    check_database_health,
    create_database_runtime,
    run_migrations,
)
from loreforge.settings import load_settings

pytestmark = pytest.mark.skipif(
    os.environ.get("LOREFORGE_RUN_LIVE_DATABASE_SMOKE") != "true",
    reason="set LOREFORGE_RUN_LIVE_DATABASE_SMOKE=true to run live database smoke test",
)


def test_live_database_health_migration_and_catalog_persistence() -> None:
    settings = load_settings()
    if settings.database.url is None:
        pytest.skip("LOREFORGE_DATABASE_URL is required for live database smoke test")

    run_migrations(settings.database)
    runtime = create_database_runtime(settings.database)
    assert runtime is not None
    try:
        assert check_database_health(runtime.session_factory).healthy is True
        repository = SqlAlchemyCatalogRepository(runtime.session_factory)
        document_id = uuid4()
        entry = CatalogEntry(
            document_id=document_id,
            filename="live-smoke.pdf",
            uploaded_at=datetime.now(timezone.utc),
            page_count=0,
            chunk_count=0,
            status=DocumentStatus.UPLOADED,
        )

        repository.add(entry)

        assert repository.get(document_id) == entry
        assert repository.remove(document_id) is True
    finally:
        runtime.close()
