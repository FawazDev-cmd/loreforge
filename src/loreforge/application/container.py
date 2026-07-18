"""Shared application service container."""

from dataclasses import dataclass

from loreforge.askme import AskMeService
from loreforge.catalog import CatalogService


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    """Immutable references to services owned by one application instance."""

    catalog_service: CatalogService
    askme_service: AskMeService

    def __post_init__(self) -> None:
        if type(self.catalog_service) is not CatalogService:
            msg = "catalog_service must be a CatalogService"
            raise TypeError(msg)
        if type(self.askme_service) is not AskMeService:
            msg = "askme_service must be an AskMeService"
            raise TypeError(msg)
