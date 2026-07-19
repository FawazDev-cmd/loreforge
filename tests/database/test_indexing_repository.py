from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from loreforge.catalog import CatalogEntry, DocumentStatus
from loreforge.database import SqlAlchemyCatalogRepository
from loreforge.database.base import Base
from loreforge.database.indexing import SqlAlchemyIndexingStateRepository
from loreforge.indexing import (
    IndexingState,
    IndexingStateRepository,
    IndexingStateRepositoryError,
    IndexingStatus,
)

STATE1 = UUID("00000000-0000-0000-0000-000000000101")
STATE2 = UUID("00000000-0000-0000-0000-000000000102")
DOC1 = UUID("00000000-0000-0000-0000-000000000001")
DOC2 = UUID("00000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


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


def test_sqlalchemy_indexing_state_repository_satisfies_protocol(
    session_factory: sessionmaker[Session],
) -> None:
    assert isinstance(
        SqlAlchemyIndexingStateRepository(session_factory),
        IndexingStateRepository,
    )


def test_indexing_state_survives_repository_recreation(
    session_factory: sessionmaker[Session],
) -> None:
    _add_document(session_factory, DOC1)
    first = SqlAlchemyIndexingStateRepository(session_factory)
    state = _state(STATE1, DOC1)

    first.add(state)
    second = SqlAlchemyIndexingStateRepository(session_factory)

    assert second.get(STATE1) == state


def test_indexing_state_list_preserves_insertion_order(
    session_factory: sessionmaker[Session],
) -> None:
    _add_document(session_factory, DOC1)
    _add_document(session_factory, DOC2)
    repository = SqlAlchemyIndexingStateRepository(session_factory)
    repository.add(_state(STATE1, DOC1))
    repository.add(_state(STATE2, DOC2))

    assert [state.state_id for state in repository.list()] == [STATE1, STATE2]


def test_list_for_document_filters_without_reordering(
    session_factory: sessionmaker[Session],
) -> None:
    _add_document(session_factory, DOC1)
    _add_document(session_factory, DOC2)
    repository = SqlAlchemyIndexingStateRepository(session_factory)
    repository.add(_state(STATE1, DOC1))
    repository.add(_state(STATE2, DOC2))

    assert repository.list_for_document(DOC1) == (_state(STATE1, DOC1),)


def test_duplicate_indexing_state_insert_is_rejected(
    session_factory: sessionmaker[Session],
) -> None:
    _add_document(session_factory, DOC1)
    repository = SqlAlchemyIndexingStateRepository(session_factory)
    repository.add(_state(STATE1, DOC1))

    with pytest.raises(IndexingStateRepositoryError, match="state_id"):
        repository.add(_state(STATE1, DOC1, status=IndexingStatus.FAILED))

    assert repository.list() == (_state(STATE1, DOC1),)


def test_indexing_state_update_replaces_existing_snapshot(
    session_factory: sessionmaker[Session],
) -> None:
    _add_document(session_factory, DOC1)
    repository = SqlAlchemyIndexingStateRepository(session_factory)
    repository.add(_state(STATE1, DOC1))
    updated = _state(
        STATE1,
        DOC1,
        status=IndexingStatus.SUCCEEDED,
        page_count=2,
        chunk_count=3,
        completed_at=NOW,
    )

    repository.update(updated)

    assert repository.get(STATE1) == updated


def test_indexing_state_update_missing_is_rejected(
    session_factory: sessionmaker[Session],
) -> None:
    repository = SqlAlchemyIndexingStateRepository(session_factory)

    with pytest.raises(IndexingStateRepositoryError, match="does not exist"):
        repository.update(_state(STATE1, DOC1))


def test_indexing_state_remove_existing_and_missing(
    session_factory: sessionmaker[Session],
) -> None:
    _add_document(session_factory, DOC1)
    repository = SqlAlchemyIndexingStateRepository(session_factory)
    repository.add(_state(STATE1, DOC1))

    assert repository.remove(STATE1) is True
    assert repository.remove(STATE1) is False
    assert repository.list() == ()


def test_indexing_state_snapshots_are_immutable_tuples(
    session_factory: sessionmaker[Session],
) -> None:
    _add_document(session_factory, DOC1)
    repository = SqlAlchemyIndexingStateRepository(session_factory)
    repository.add(_state(STATE1, DOC1))
    snapshot = repository.list()

    snapshot += (_state(STATE2, DOC1),)

    assert repository.list() == (_state(STATE1, DOC1),)


def _add_document(session_factory: sessionmaker[Session], document_id: UUID) -> None:
    SqlAlchemyCatalogRepository(session_factory).add(
        CatalogEntry(
            document_id=document_id,
            filename=f"{document_id}.pdf",
            uploaded_at=NOW,
            page_count=0,
            chunk_count=0,
            status=DocumentStatus.UPLOADED,
        )
    )


def _state(
    state_id: UUID,
    document_id: UUID,
    *,
    status: IndexingStatus = IndexingStatus.STARTED,
    page_count: int = 0,
    chunk_count: int = 0,
    completed_at: datetime | None = None,
    error_message: str | None = None,
) -> IndexingState:
    return IndexingState(
        state_id=state_id,
        document_id=document_id,
        status=status,
        started_at=NOW,
        updated_at=NOW,
        page_count=page_count,
        chunk_count=chunk_count,
        completed_at=completed_at,
        error_message=error_message,
    )
