from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from loreforge.catalog import (
    CatalogEntry,
    CatalogRepository,
    CatalogRepositoryError,
    DocumentStatus,
)
from loreforge.database import (
    DatabaseHealth,
    SqlAlchemyCatalogRepository,
    check_database_health,
    normalize_database_url,
)
from loreforge.database.base import Base

DOC1 = UUID("00000000-0000-0000-0000-000000000001")
DOC2 = UUID("00000000-0000-0000-0000-000000000002")
UPLOADED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def engine() -> Iterator[Engine]:
    database_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(database_engine)
    try:
        yield database_engine
    finally:
        database_engine.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_normalize_database_url_selects_psycopg_driver() -> None:
    assert normalize_database_url("postgres://user:pass@host/db") == (
        "postgresql+psycopg://user:pass@host/db"
    )
    assert normalize_database_url("postgresql://user:pass@host/db") == (
        "postgresql+psycopg://user:pass@host/db"
    )
    assert normalize_database_url("postgresql+psycopg://user:pass@host/db") == (
        "postgresql+psycopg://user:pass@host/db"
    )


def test_database_health_uses_simple_query(
    session_factory: sessionmaker[Session],
) -> None:
    assert check_database_health(session_factory) == DatabaseHealth(healthy=True)


def test_sqlalchemy_catalog_repository_satisfies_protocol(
    session_factory: sessionmaker[Session],
) -> None:
    assert isinstance(SqlAlchemyCatalogRepository(session_factory), CatalogRepository)


def test_catalog_metadata_survives_repository_recreation(
    session_factory: sessionmaker[Session],
) -> None:
    first = SqlAlchemyCatalogRepository(session_factory)
    entry = _entry(DOC1)

    first.add(entry)
    second = SqlAlchemyCatalogRepository(session_factory)

    assert second.get(DOC1) == entry


def test_catalog_list_preserves_insertion_order(
    session_factory: sessionmaker[Session],
) -> None:
    repository = SqlAlchemyCatalogRepository(session_factory)
    repository.add(_entry(DOC1))
    repository.add(_entry(DOC2, filename="handbook.pdf"))

    assert [entry.document_id for entry in repository.list()] == [DOC1, DOC2]


def test_catalog_duplicate_insert_is_rejected_and_rolled_back(
    session_factory: sessionmaker[Session],
) -> None:
    repository = SqlAlchemyCatalogRepository(session_factory)
    entry = _entry(DOC1)
    repository.add(entry)

    with pytest.raises(CatalogRepositoryError, match="document_id"):
        repository.add(_entry(DOC1, filename="other.pdf"))

    assert repository.list() == (entry,)


def test_catalog_update_replaces_existing_snapshot(
    session_factory: sessionmaker[Session],
) -> None:
    repository = SqlAlchemyCatalogRepository(session_factory)
    repository.add(_entry(DOC1))
    updated = _entry(DOC1, status=DocumentStatus.READY, page_count=2, chunk_count=4)

    repository.update(updated)

    assert repository.get(DOC1) == updated


def test_catalog_update_missing_entry_is_rejected(
    session_factory: sessionmaker[Session],
) -> None:
    repository = SqlAlchemyCatalogRepository(session_factory)

    with pytest.raises(CatalogRepositoryError, match="does not exist"):
        repository.update(_entry(DOC1))


def test_catalog_remove_existing_and_missing_entries(
    session_factory: sessionmaker[Session],
) -> None:
    repository = SqlAlchemyCatalogRepository(session_factory)
    repository.add(_entry(DOC1))

    assert repository.remove(DOC1) is True
    assert repository.remove(DOC1) is False
    assert repository.get(DOC1) is None


def test_catalog_snapshots_are_immutable_tuples(
    session_factory: sessionmaker[Session],
) -> None:
    repository = SqlAlchemyCatalogRepository(session_factory)
    repository.add(_entry(DOC1))
    snapshot = repository.list()

    snapshot += (_entry(DOC2, filename="handbook.pdf"),)

    assert repository.list() == (_entry(DOC1),)


def _entry(
    document_id: UUID,
    *,
    filename: str = "policy.pdf",
    status: DocumentStatus = DocumentStatus.UPLOADED,
    page_count: int = 0,
    chunk_count: int = 0,
) -> CatalogEntry:
    return CatalogEntry(
        document_id=document_id,
        filename=filename,
        uploaded_at=UPLOADED_AT,
        page_count=page_count,
        chunk_count=chunk_count,
        status=status,
    )
