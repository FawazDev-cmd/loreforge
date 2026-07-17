"""Catalog repository protocol and in-memory implementation."""

from typing import Protocol, runtime_checkable
from uuid import UUID

from loreforge.catalog.models import CatalogEntry


class CatalogRepositoryError(ValueError):
    """Raised when catalog repository state would become invalid."""


@runtime_checkable
class CatalogRepository(Protocol):
    """Repository for knowledge-base catalog entries."""

    def add(self, entry: CatalogEntry) -> None:
        """Add one catalog entry."""
        ...

    def get(self, document_id: UUID) -> CatalogEntry | None:
        """Return a catalog entry by document ID when present."""
        ...

    def list(self) -> tuple[CatalogEntry, ...]:
        """Return catalog entries in insertion order."""
        ...

    def update(self, entry: CatalogEntry) -> None:
        """Replace an existing catalog entry."""
        ...

    def remove(self, document_id: UUID) -> bool:
        """Remove a catalog entry by document ID."""
        ...


class InMemoryCatalogRepository:
    """Deterministic in-memory catalog repository."""

    def __init__(self) -> None:
        self._entries: dict[UUID, CatalogEntry] = {}

    def add(self, entry: CatalogEntry) -> None:
        if entry.document_id in self._entries:
            msg = "document_id already exists in catalog"
            raise CatalogRepositoryError(msg)
        self._entries[entry.document_id] = entry

    def get(self, document_id: UUID) -> CatalogEntry | None:
        return self._entries.get(document_id)

    def list(self) -> tuple[CatalogEntry, ...]:
        return tuple(self._entries.values())

    def update(self, entry: CatalogEntry) -> None:
        if entry.document_id not in self._entries:
            msg = "document_id does not exist in catalog"
            raise CatalogRepositoryError(msg)
        self._entries[entry.document_id] = entry

    def remove(self, document_id: UUID) -> bool:
        if document_id not in self._entries:
            return False
        del self._entries[document_id]
        return True
