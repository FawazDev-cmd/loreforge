"""SQLAlchemy catalog repository adapter."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from loreforge.catalog import CatalogEntry, CatalogRepositoryError, DocumentStatus
from loreforge.database.engine import SessionFactory
from loreforge.database.models import DocumentRecord


class SqlAlchemyCatalogRepository:
    """Durable catalog repository backed by SQLAlchemy sessions."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(self, entry: CatalogEntry) -> None:
        record = DocumentRecord(
            document_id=entry.document_id,
            filename=entry.filename,
            uploaded_at=entry.uploaded_at,
            page_count=entry.page_count,
            chunk_count=entry.chunk_count,
            status=entry.status.value,
            owner_user_id=entry.owner_user_id,
        )
        try:
            with self._session_factory() as session, session.begin():
                session.add(record)
        except IntegrityError as exc:
            msg = "document_id already exists in catalog"
            raise CatalogRepositoryError(msg) from exc

    def get(self, document_id: UUID) -> CatalogEntry | None:
        with self._session_factory() as session:
            record = _get_record(session, document_id)
            if record is None:
                return None
            return _entry_from_record(record)

    def list(self) -> tuple[CatalogEntry, ...]:
        statement = select(DocumentRecord).order_by(DocumentRecord.row_id)
        with self._session_factory() as session:
            return tuple(
                _entry_from_record(record) for record in session.scalars(statement)
            )

    def update(self, entry: CatalogEntry) -> None:
        with self._session_factory() as session, session.begin():
            record = _get_record(session, entry.document_id)
            if record is None:
                msg = "document_id does not exist in catalog"
                raise CatalogRepositoryError(msg)
            record.filename = entry.filename
            record.uploaded_at = entry.uploaded_at
            record.page_count = entry.page_count
            record.chunk_count = entry.chunk_count
            record.status = entry.status.value
            record.owner_user_id = entry.owner_user_id

    def remove(self, document_id: UUID) -> bool:
        with self._session_factory() as session, session.begin():
            record = _get_record(session, document_id)
            if record is None:
                return False
            session.delete(record)
            return True


def _get_record(session: Session, document_id: UUID) -> DocumentRecord | None:
    statement = select(DocumentRecord).where(DocumentRecord.document_id == document_id)
    return session.scalar(statement)


def _entry_from_record(record: DocumentRecord) -> CatalogEntry:
    return CatalogEntry(
        document_id=record.document_id,
        filename=record.filename,
        uploaded_at=_ensure_utc(record.uploaded_at),
        page_count=record.page_count,
        chunk_count=record.chunk_count,
        status=DocumentStatus(record.status),
        owner_user_id=record.owner_user_id,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
