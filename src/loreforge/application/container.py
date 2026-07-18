"""Shared application service container."""

from dataclasses import dataclass

from loreforge.askme import AskMeService
from loreforge.catalog import CatalogService
from loreforge.indexing import DocumentIndexingService


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    """Immutable references to services owned by one application instance."""

    catalog_service: CatalogService
    askme_service: AskMeService
    document_indexing_service: DocumentIndexingService

    def __post_init__(self) -> None:
        if type(self.catalog_service) is not CatalogService:
            msg = "catalog_service must be a CatalogService"
            raise TypeError(msg)
        if type(self.askme_service) is not AskMeService:
            msg = "askme_service must be an AskMeService"
            raise TypeError(msg)
        if type(self.document_indexing_service) is not DocumentIndexingService:
            msg = "document_indexing_service must be a DocumentIndexingService"
            raise TypeError(msg)
