"""Immutable knowledge-base catalog models."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID


class DocumentStatus(StrEnum):
    """Lifecycle status for a cataloged document."""

    UPLOADED = "UPLOADED"
    INGESTING = "INGESTING"
    READY = "READY"
    FAILED = "FAILED"
    DELETED = "DELETED"


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """Immutable metadata for one knowledge-base document."""

    document_id: UUID
    filename: str
    uploaded_at: datetime
    page_count: int
    chunk_count: int
    status: DocumentStatus

    def __post_init__(self) -> None:
        if not self.filename.strip():
            msg = "filename must not be empty"
            raise ValueError(msg)
        if self.uploaded_at.tzinfo is None or self.uploaded_at.utcoffset() is None:
            msg = "uploaded_at must be timezone-aware"
            raise ValueError(msg)
        if self.uploaded_at.utcoffset() != timezone.utc.utcoffset(self.uploaded_at):
            msg = "uploaded_at must be UTC"
            raise ValueError(msg)
        _validate_nonnegative_int(self.page_count, "page_count")
        _validate_nonnegative_int(self.chunk_count, "chunk_count")
        if type(self.status) is not DocumentStatus:
            msg = "status must be a DocumentStatus"
            raise ValueError(msg)


def _validate_nonnegative_int(value: int, name: str) -> None:
    value_object: object = value
    if type(value_object) is not int:
        msg = f"{name} must be an integer"
        raise ValueError(msg)
    if value < 0:
        msg = f"{name} must be greater than or equal to zero"
        raise ValueError(msg)
