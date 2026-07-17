"""Framework-independent knowledge-base catalog."""

from loreforge.catalog.models import CatalogEntry, DocumentStatus
from loreforge.catalog.repository import (
    CatalogRepository,
    CatalogRepositoryError,
    InMemoryCatalogRepository,
)
from loreforge.catalog.service import CatalogService, CatalogServiceError

__all__ = [
    "CatalogEntry",
    "CatalogRepository",
    "CatalogRepositoryError",
    "CatalogService",
    "CatalogServiceError",
    "DocumentStatus",
    "InMemoryCatalogRepository",
]
