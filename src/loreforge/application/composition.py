"""Application-level service construction."""

from collections.abc import Callable
from dataclasses import dataclass

from loreforge.application.container import ApplicationContainer
from loreforge.askme import AskMeService, AskMeUnavailableError
from loreforge.catalog import CatalogService, InMemoryCatalogRepository
from loreforge.documents.ingestion import ingest_pdf
from loreforge.embeddings.provider import EmbeddingProvider
from loreforge.generation.validation_models import ValidatedGroundedAnswer
from loreforge.indexing import DocumentIndexingService, PdfIngestor
from loreforge.retrieval.bm25 import InMemoryBM25Index
from loreforge.vector_index import InMemoryVectorIndex

_UNAVAILABLE_DETAIL = "AskMe is temporarily unavailable."


class UnavailableGroundedQueryEngine:
    """Grounded-query engine used until concrete runtime dependencies are wired."""

    def answer(self, question: str) -> ValidatedGroundedAnswer:
        raise AskMeUnavailableError(_UNAVAILABLE_DETAIL)


@dataclass(frozen=True, slots=True)
class CompositionFactories:
    """Optional service factories for application assembly tests or deployments."""

    askme_service_factory: Callable[[], AskMeService] | None = None
    document_ingestor_factory: Callable[[], PdfIngestor] | None = None
    document_embedding_provider_factory: Callable[[], EmbeddingProvider] | None = None
    document_indexing_service_factory: (
        Callable[[CatalogService], DocumentIndexingService] | None
    ) = None


def create_application_container(
    *,
    factories: CompositionFactories | None = None,
) -> ApplicationContainer:
    """Create one isolated set of application services."""
    catalog_service = CatalogService(InMemoryCatalogRepository())
    askme_service = _create_askme_service(factories)
    document_indexing_service = _create_document_indexing_service(
        catalog_service=catalog_service,
        factories=factories,
    )
    return ApplicationContainer(
        catalog_service=catalog_service,
        askme_service=askme_service,
        document_indexing_service=document_indexing_service,
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


def _create_document_indexing_service(
    *,
    catalog_service: CatalogService,
    factories: CompositionFactories | None,
) -> DocumentIndexingService:
    if (
        factories is not None
        and factories.document_indexing_service_factory is not None
    ):
        service = factories.document_indexing_service_factory(catalog_service)
        if type(service) is not DocumentIndexingService:
            msg = (
                "document_indexing_service_factory must return "
                "a DocumentIndexingService"
            )
            raise TypeError(msg)
        return service

    vector_index = InMemoryVectorIndex()
    lexical_index = InMemoryBM25Index()
    ingestor = _create_document_ingestor(factories)
    embedding_provider = _create_document_embedding_provider(factories)
    return DocumentIndexingService(
        catalog_service=catalog_service,
        ingestor=ingestor,
        embedding_provider=embedding_provider,
        vector_index=vector_index,
        lexical_index=lexical_index,
    )


def _create_document_ingestor(factories: CompositionFactories | None) -> PdfIngestor:
    if factories is None or factories.document_ingestor_factory is None:
        return ingest_pdf
    return factories.document_ingestor_factory()


def _create_document_embedding_provider(
    factories: CompositionFactories | None,
) -> EmbeddingProvider | None:
    if factories is None or factories.document_embedding_provider_factory is None:
        return None
    return factories.document_embedding_provider_factory()


def _unavailable_askme_service() -> AskMeService:
    return AskMeService(query_engine=UnavailableGroundedQueryEngine())
