"""Application-level service construction."""

from collections.abc import Callable
from dataclasses import dataclass

from loreforge.application.container import ApplicationContainer
from loreforge.askme import AskMeService, AskMeUnavailableError
from loreforge.catalog import CatalogService, InMemoryCatalogRepository
from loreforge.generation.validation_models import ValidatedGroundedAnswer

_UNAVAILABLE_DETAIL = "AskMe is temporarily unavailable."


class UnavailableGroundedQueryEngine:
    """Grounded-query engine used until concrete runtime dependencies are wired."""

    def answer(self, question: str) -> ValidatedGroundedAnswer:
        raise AskMeUnavailableError(_UNAVAILABLE_DETAIL)


@dataclass(frozen=True, slots=True)
class CompositionFactories:
    """Optional service factories for application assembly tests or deployments."""

    askme_service_factory: Callable[[], AskMeService] | None = None


def create_application_container(
    *,
    factories: CompositionFactories | None = None,
) -> ApplicationContainer:
    """Create one isolated set of application services."""
    catalog_service = CatalogService(InMemoryCatalogRepository())
    askme_service = _create_askme_service(factories)
    return ApplicationContainer(
        catalog_service=catalog_service,
        askme_service=askme_service,
    )


def _create_askme_service(factories: CompositionFactories | None) -> AskMeService:
    if factories is None or factories.askme_service_factory is None:
        return _unavailable_askme_service()

    try:
        service = factories.askme_service_factory()
    except AskMeUnavailableError:
        return _unavailable_askme_service()

    if type(service) is not AskMeService:
        msg = "askme_service_factory must return an AskMeService"
        raise TypeError(msg)
    return service


def _unavailable_askme_service() -> AskMeService:
    return AskMeService(query_engine=UnavailableGroundedQueryEngine())
