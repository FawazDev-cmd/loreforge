"""Application-level service construction."""

from collections.abc import Callable
from dataclasses import dataclass

from loreforge.application.container import ApplicationContainer
from loreforge.askme import AskMeService, AskMeUnavailableError
from loreforge.catalog import CatalogService, InMemoryCatalogRepository
from loreforge.documents.ingestion import ingest_pdf
from loreforge.embeddings.provider import EmbeddingProvider, QueryEmbeddingProvider
from loreforge.generation.provider import LLMProvider
from loreforge.generation.validation_models import ValidatedGroundedAnswer
from loreforge.indexing import DocumentIndexingService, PdfIngestor
from loreforge.observability import InMemoryMetricsRecorder
from loreforge.query import ProductionGroundedQueryEngine
from loreforge.reranking import RerankerProvider
from loreforge.retrieval.bm25 import InMemoryBM25Index
from loreforge.settings import (
    LoreForgeSettings,
    ProviderSelection,
    SettingsError,
    load_settings,
)
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
    query_embedding_provider_factory: Callable[[], QueryEmbeddingProvider] | None = None
    reranker_provider_factory: Callable[[], RerankerProvider] | None = None
    llm_provider_factory: Callable[[], LLMProvider] | None = None
    document_indexing_service_factory: (
        Callable[
            [CatalogService, InMemoryVectorIndex, InMemoryBM25Index],
            DocumentIndexingService,
        ]
        | None
    ) = None


def create_application_container(
    *,
    factories: CompositionFactories | None = None,
    settings: LoreForgeSettings | None = None,
) -> ApplicationContainer:
    """Create one isolated set of application services."""
    runtime_settings = load_settings() if settings is None else settings
    catalog_service = CatalogService(InMemoryCatalogRepository())
    vector_index = InMemoryVectorIndex()
    lexical_index = InMemoryBM25Index()
    metrics_recorder = InMemoryMetricsRecorder()
    document_indexing_service = _create_document_indexing_service(
        catalog_service=catalog_service,
        vector_index=vector_index,
        lexical_index=lexical_index,
        factories=factories,
        settings=runtime_settings,
    )
    query_engine = _create_query_engine(
        vector_index=vector_index,
        lexical_index=lexical_index,
        factories=factories,
        metrics_recorder=metrics_recorder,
        settings=runtime_settings,
    )
    askme_service = _create_askme_service(
        factories=factories,
        query_engine=query_engine,
    )
    return ApplicationContainer(
        catalog_service=catalog_service,
        askme_service=askme_service,
        document_indexing_service=document_indexing_service,
        vector_index=vector_index,
        lexical_index=lexical_index,
        query_engine=query_engine,
        metrics_recorder=metrics_recorder,
        settings=runtime_settings,
    )


def _create_askme_service(
    *,
    factories: CompositionFactories | None,
    query_engine: ProductionGroundedQueryEngine | None,
) -> AskMeService:
    if factories is not None and factories.askme_service_factory is not None:
        try:
            service = factories.askme_service_factory()
        except AskMeUnavailableError:
            return _unavailable_askme_service()
        if type(service) is not AskMeService:
            msg = "askme_service_factory must return an AskMeService"
            raise TypeError(msg)
        return service

    if query_engine is None:
        return _unavailable_askme_service()
    return AskMeService(query_engine=query_engine)


def _create_document_indexing_service(
    *,
    catalog_service: CatalogService,
    vector_index: InMemoryVectorIndex,
    lexical_index: InMemoryBM25Index,
    factories: CompositionFactories | None,
    settings: LoreForgeSettings,
) -> DocumentIndexingService:
    if (
        factories is not None
        and factories.document_indexing_service_factory is not None
    ):
        service = factories.document_indexing_service_factory(
            catalog_service,
            vector_index,
            lexical_index,
        )
        if type(service) is not DocumentIndexingService:
            msg = (
                "document_indexing_service_factory must return "
                "a DocumentIndexingService"
            )
            raise TypeError(msg)
        return service

    ingestor = _create_document_ingestor(factories)
    embedding_provider = _create_document_embedding_provider(factories, settings)
    return DocumentIndexingService(
        catalog_service=catalog_service,
        ingestor=ingestor,
        embedding_provider=embedding_provider,
        vector_index=vector_index,
        lexical_index=lexical_index,
    )


def _create_query_engine(
    *,
    vector_index: InMemoryVectorIndex,
    lexical_index: InMemoryBM25Index,
    factories: CompositionFactories | None,
    metrics_recorder: InMemoryMetricsRecorder,
    settings: LoreForgeSettings,
) -> ProductionGroundedQueryEngine | None:
    query_embedder = _create_query_embedding_provider(factories, settings)
    reranker = _create_reranker_provider(factories, settings)
    answer_generator = _create_llm_provider(factories, settings)
    if query_embedder is None or reranker is None or answer_generator is None:
        return None

    return ProductionGroundedQueryEngine(
        query_embedder=query_embedder,
        semantic_retriever=vector_index,
        lexical_retriever=lexical_index,
        reranker=reranker,
        answer_generator=answer_generator,
        metrics_recorder=metrics_recorder,
    )


def _create_document_ingestor(factories: CompositionFactories | None) -> PdfIngestor:
    if factories is None or factories.document_ingestor_factory is None:
        return ingest_pdf
    return factories.document_ingestor_factory()


def _create_document_embedding_provider(
    factories: CompositionFactories | None,
    settings: LoreForgeSettings,
) -> EmbeddingProvider | None:
    if (
        factories is not None
        and factories.document_embedding_provider_factory is not None
    ):
        return factories.document_embedding_provider_factory()
    provider = _embedding_provider_from_settings(
        selection=settings.providers.document_embeddings,
        settings=settings,
    )
    if provider is None:
        return None
    if not isinstance(provider, EmbeddingProvider):
        msg = "configured document embedding provider must support embeddings"
        raise TypeError(msg)
    return provider


def _create_query_embedding_provider(
    factories: CompositionFactories | None,
    settings: LoreForgeSettings,
) -> QueryEmbeddingProvider | None:
    if factories is not None and factories.query_embedding_provider_factory is not None:
        return factories.query_embedding_provider_factory()
    provider = _embedding_provider_from_settings(
        selection=settings.providers.query_embeddings,
        settings=settings,
    )
    if provider is None:
        return None
    if not isinstance(provider, QueryEmbeddingProvider):
        msg = "configured query embedding provider must support query embeddings"
        raise TypeError(msg)
    return provider


def _embedding_provider_from_settings(
    *,
    selection: ProviderSelection,
    settings: LoreForgeSettings,
) -> EmbeddingProvider | QueryEmbeddingProvider | None:
    if selection == ProviderSelection.DISABLED:
        return None
    if selection == ProviderSelection.LOCAL:
        from loreforge.embeddings.local import LocalSentenceTransformerProvider

        return LocalSentenceTransformerProvider(
            model_name=settings.providers.local.embedding_model,
            batch_size=settings.providers.local.batch_size,
        )
    if selection == ProviderSelection.GEMINI:
        from loreforge.embeddings.gemini import (
            GeminiEmbeddingConfig,
            GeminiEmbeddingProvider,
        )

        gemini = settings.providers.gemini
        return GeminiEmbeddingProvider(
            GeminiEmbeddingConfig(
                api_key=_required(gemini.api_key, "LOREFORGE_GEMINI_API_KEY"),
                model=_required(
                    gemini.embedding_model,
                    "LOREFORGE_GEMINI_EMBEDDING_MODEL",
                ),
                timeout_seconds=gemini.timeout_seconds,
            )
        )
    msg = "unsupported embedding provider selection"
    raise SettingsError(msg)


def _create_reranker_provider(
    factories: CompositionFactories | None,
    settings: LoreForgeSettings,
) -> RerankerProvider | None:
    if factories is not None and factories.reranker_provider_factory is not None:
        return factories.reranker_provider_factory()
    if settings.providers.reranker == ProviderSelection.DISABLED:
        return None
    if settings.providers.reranker == ProviderSelection.LOCAL:
        from loreforge.reranking.local import LocalCrossEncoderReranker

        return LocalCrossEncoderReranker(
            model_name=settings.providers.local.reranker_model,
            batch_size=settings.providers.local.batch_size,
        )
    msg = "unsupported reranker provider selection"
    raise SettingsError(msg)


def _create_llm_provider(
    factories: CompositionFactories | None,
    settings: LoreForgeSettings,
) -> LLMProvider | None:
    if factories is not None and factories.llm_provider_factory is not None:
        return factories.llm_provider_factory()
    if settings.providers.llm == ProviderSelection.DISABLED:
        return None
    if settings.providers.llm == ProviderSelection.GEMINI:
        from loreforge.generation.gemini import (
            GeminiGenerationConfig,
            GeminiLLMProvider,
        )

        gemini = settings.providers.gemini
        return GeminiLLMProvider(
            GeminiGenerationConfig(
                api_key=_required(gemini.api_key, "LOREFORGE_GEMINI_API_KEY"),
                model=_required(
                    gemini.generation_model,
                    "LOREFORGE_GEMINI_GENERATION_MODEL",
                ),
                timeout_seconds=gemini.timeout_seconds,
            )
        )
    if settings.providers.llm == ProviderSelection.OPENROUTER:
        from loreforge.generation.openrouter import (
            OpenRouterConfig,
            OpenRouterLLMProvider,
        )

        openrouter = settings.providers.openrouter
        return OpenRouterLLMProvider(
            OpenRouterConfig(
                api_key=_required(
                    openrouter.api_key,
                    "LOREFORGE_OPENROUTER_API_KEY",
                ),
                model=_required(openrouter.model, "LOREFORGE_OPENROUTER_MODEL"),
                base_url=openrouter.base_url,
                timeout_seconds=openrouter.timeout_seconds,
            )
        )
    msg = "unsupported LLM provider selection"
    raise SettingsError(msg)


def _required(value: str | None, name: str) -> str:
    if value is None:
        msg = f"{name} is required"
        raise SettingsError(msg)
    return value


def _unavailable_askme_service() -> AskMeService:
    return AskMeService(query_engine=UnavailableGroundedQueryEngine())
