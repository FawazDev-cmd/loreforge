"""Knowledge-base catalog lifecycle service."""

from dataclasses import replace
from datetime import datetime
from uuid import UUID, uuid4

from loreforge.catalog.models import CatalogEntry, DocumentStatus
from loreforge.catalog.repository import CatalogRepository


class CatalogServiceError(ValueError):
    """Raised when catalog service lifecycle rules are violated."""


class CatalogService:
    """Coordinate document catalog registration and lifecycle transitions."""

    _ALLOWED_TRANSITIONS = {
        DocumentStatus.UPLOADED: frozenset(
            {DocumentStatus.INGESTING, DocumentStatus.FAILED}
        ),
        DocumentStatus.INGESTING: frozenset(
            {DocumentStatus.READY, DocumentStatus.FAILED}
        ),
        DocumentStatus.READY: frozenset({DocumentStatus.DELETED}),
        DocumentStatus.FAILED: frozenset({DocumentStatus.DELETED}),
        DocumentStatus.DELETED: frozenset(),
    }

    def __init__(self, repository: CatalogRepository) -> None:
        self._repository = repository

    def register_upload(
        self,
        *,
        filename: str,
        uploaded_at: datetime,
        page_count: int = 0,
        document_id: UUID | None = None,
        owner_user_id: UUID | None = None,
    ) -> CatalogEntry:
        """Register newly uploaded document metadata."""
        entry = CatalogEntry(
            document_id=document_id or uuid4(),
            filename=filename,
            uploaded_at=uploaded_at,
            page_count=page_count,
            chunk_count=0,
            status=DocumentStatus.UPLOADED,
            owner_user_id=owner_user_id,
        )
        self._repository.add(entry)
        return entry

    def mark_ingesting(self, document_id: UUID) -> CatalogEntry:
        """Mark an uploaded document as actively ingesting."""
        return self._transition(document_id, DocumentStatus.INGESTING)

    def mark_ingesting_for_owner(
        self,
        document_id: UUID,
        owner_user_id: UUID,
    ) -> CatalogEntry:
        """Mark an owned uploaded document as actively ingesting."""
        self._require_owner(document_id, owner_user_id)
        return self.mark_ingesting(document_id)

    def mark_ready(
        self,
        document_id: UUID,
        *,
        page_count: int,
        chunk_count: int,
    ) -> CatalogEntry:
        """Mark an ingesting document as ready with final counts."""
        current = self._require_entry(document_id)
        self._validate_transition(current.status, DocumentStatus.READY)
        updated = replace(
            current,
            page_count=page_count,
            chunk_count=chunk_count,
            status=DocumentStatus.READY,
        )
        self._repository.update(updated)
        return updated

    def mark_failed(self, document_id: UUID) -> CatalogEntry:
        """Mark an uploaded or ingesting document as failed."""
        return self._transition(document_id, DocumentStatus.FAILED)

    def mark_failed_for_owner(
        self,
        document_id: UUID,
        owner_user_id: UUID,
    ) -> CatalogEntry:
        """Mark an owned uploaded or ingesting document as failed."""
        self._require_owner(document_id, owner_user_id)
        return self.mark_failed(document_id)

    def mark_deleted(self, document_id: UUID) -> CatalogEntry:
        """Mark a ready or failed document as deleted."""
        return self._transition(document_id, DocumentStatus.DELETED)

    def mark_deleted_for_owner(
        self,
        document_id: UUID,
        owner_user_id: UUID,
    ) -> CatalogEntry:
        """Mark an owned ready or failed document as deleted."""
        self._require_owner(document_id, owner_user_id)
        return self.mark_deleted(document_id)

    def get(self, document_id: UUID) -> CatalogEntry | None:
        """Return a catalog entry by document ID when present."""
        return self._repository.get(document_id)

    def get_for_owner(
        self,
        document_id: UUID,
        owner_user_id: UUID,
    ) -> CatalogEntry | None:
        """Return an owned catalog entry without revealing other owners."""
        entry = self._repository.get(document_id)
        if entry is None or entry.owner_user_id != owner_user_id:
            return None
        return entry

    def list(self) -> tuple[CatalogEntry, ...]:
        """Return catalog entries in repository order."""
        return self._repository.list()

    def list_for_owner(self, owner_user_id: UUID) -> tuple[CatalogEntry, ...]:
        """Return catalog entries owned by one user in repository order."""
        return tuple(
            entry
            for entry in self._repository.list()
            if entry.owner_user_id == owner_user_id
        )

    def mark_ready_for_owner(
        self,
        document_id: UUID,
        owner_user_id: UUID,
        *,
        page_count: int,
        chunk_count: int,
    ) -> CatalogEntry:
        """Mark an owned ingesting document as ready with final counts."""
        self._require_owner(document_id, owner_user_id)
        return self.mark_ready(
            document_id,
            page_count=page_count,
            chunk_count=chunk_count,
        )

    def _transition(
        self,
        document_id: UUID,
        target_status: DocumentStatus,
    ) -> CatalogEntry:
        current = self._require_entry(document_id)
        self._validate_transition(current.status, target_status)
        updated = replace(current, status=target_status)
        self._repository.update(updated)
        return updated

    def _require_entry(self, document_id: UUID) -> CatalogEntry:
        entry = self._repository.get(document_id)
        if entry is None:
            msg = "document_id does not exist in catalog"
            raise CatalogServiceError(msg)
        return entry

    def _require_owner(
        self,
        document_id: UUID,
        owner_user_id: UUID,
    ) -> CatalogEntry:
        entry = self._require_entry(document_id)
        if entry.owner_user_id != owner_user_id:
            msg = "document_id does not exist in catalog"
            raise CatalogServiceError(msg)
        return entry

    def _validate_transition(
        self,
        current_status: DocumentStatus,
        target_status: DocumentStatus,
    ) -> None:
        if target_status not in self._ALLOWED_TRANSITIONS[current_status]:
            msg = f"cannot transition from {current_status} to {target_status}"
            raise CatalogServiceError(msg)
