"""SQLAlchemy indexing-state repository adapter."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from loreforge.database.engine import SessionFactory
from loreforge.database.models import IndexingStateRecord
from loreforge.indexing.state import (
    IndexingState,
    IndexingStateRepositoryError,
    IndexingStatus,
)


class SqlAlchemyIndexingStateRepository:
    """Durable indexing-state repository backed by SQLAlchemy sessions."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(self, state: IndexingState) -> None:
        record = IndexingStateRecord(
            state_id=state.state_id,
            document_id=state.document_id,
            status=state.status.value,
            started_at=state.started_at,
            updated_at=state.updated_at,
            page_count=state.page_count,
            chunk_count=state.chunk_count,
            completed_at=state.completed_at,
            error_message=state.error_message,
        )
        try:
            with self._session_factory() as session, session.begin():
                session.add(record)
        except IntegrityError as exc:
            msg = "state_id already exists in indexing state"
            raise IndexingStateRepositoryError(msg) from exc

    def get(self, state_id: UUID) -> IndexingState | None:
        with self._session_factory() as session:
            record = _get_record(session, state_id)
            if record is None:
                return None
            return _state_from_record(record)

    def list(self) -> tuple[IndexingState, ...]:
        statement = select(IndexingStateRecord).order_by(IndexingStateRecord.row_id)
        with self._session_factory() as session:
            return tuple(
                _state_from_record(record) for record in session.scalars(statement)
            )

    def list_for_document(self, document_id: UUID) -> tuple[IndexingState, ...]:
        statement = (
            select(IndexingStateRecord)
            .where(IndexingStateRecord.document_id == document_id)
            .order_by(IndexingStateRecord.row_id)
        )
        with self._session_factory() as session:
            return tuple(
                _state_from_record(record) for record in session.scalars(statement)
            )

    def update(self, state: IndexingState) -> None:
        with self._session_factory() as session, session.begin():
            record = _get_record(session, state.state_id)
            if record is None:
                msg = "state_id does not exist in indexing state"
                raise IndexingStateRepositoryError(msg)
            record.document_id = state.document_id
            record.status = state.status.value
            record.started_at = state.started_at
            record.updated_at = state.updated_at
            record.page_count = state.page_count
            record.chunk_count = state.chunk_count
            record.completed_at = state.completed_at
            record.error_message = state.error_message

    def remove(self, state_id: UUID) -> bool:
        with self._session_factory() as session, session.begin():
            record = _get_record(session, state_id)
            if record is None:
                return False
            session.delete(record)
            return True


def _get_record(session: Session, state_id: UUID) -> IndexingStateRecord | None:
    statement = select(IndexingStateRecord).where(
        IndexingStateRecord.state_id == state_id
    )
    return session.scalar(statement)


def _state_from_record(record: IndexingStateRecord) -> IndexingState:
    return IndexingState(
        state_id=record.state_id,
        document_id=record.document_id,
        status=IndexingStatus(record.status),
        started_at=_ensure_utc(record.started_at),
        updated_at=_ensure_utc(record.updated_at),
        page_count=record.page_count,
        chunk_count=record.chunk_count,
        completed_at=(
            None if record.completed_at is None else _ensure_utc(record.completed_at)
        ),
        error_message=record.error_message,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
