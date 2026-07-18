from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from loreforge.application import (
    ApplicationContainer,
    CompositionFactories,
    create_application_container,
)
from loreforge.askme import AskMeRequest, AskMeService, AskMeUnavailableError
from loreforge.catalog import CatalogService, InMemoryCatalogRepository
from loreforge.documents.models import DocumentChunk, DocumentSource
from loreforge.embeddings import EmbeddingRequest, EmbeddingResult, EmbeddingVector
from loreforge.embeddings.pipeline import EmbeddedChunk
from loreforge.generation.answer_models import GroundedAnswer, SourceReference
from loreforge.generation.evidence import EvidenceContext, EvidenceItem
from loreforge.generation.models import GenerationRequest, GenerationResponse
from loreforge.generation.validation_models import (
    CitationValidationResult,
    ValidatedGroundedAnswer,
)
from loreforge.indexing import DocumentIndexingService
from loreforge.main import create_app
from loreforge.query import ProductionGroundedQueryEngine
from loreforge.reranking import RerankingRequest, RerankingScore
from loreforge.retrieval.bm25 import InMemoryBM25Index
from loreforge.vector_index import InMemoryVectorIndex

REQUEST_ID = UUID("00000000-0000-0000-0000-000000000001")
DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000201")
CHUNK_ID = UUID("00000000-0000-0000-0000-000000000101")
QUESTION = "What is the refund policy?"
ANSWER = "Refund requests must be submitted within 14 days [S1]."
UPLOADED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeEngine:
    def __init__(self, answer: ValidatedGroundedAnswer) -> None:
        self.answer_value = answer
        self.questions: list[str] = []

    def answer(self, question: str) -> ValidatedGroundedAnswer:
        self.questions.append(question)
        return self.answer_value


class CountingContainerFactory:
    def __init__(self, container: ApplicationContainer) -> None:
        self.container = container
        self.calls = 0

    def __call__(self) -> ApplicationContainer:
        self.calls += 1
        return self.container


def test_default_composition_creates_application_container() -> None:
    container = create_application_container()

    assert type(container) is ApplicationContainer
    assert type(container.catalog_service) is CatalogService
    assert type(container.askme_service) is AskMeService
    assert type(container.document_indexing_service) is DocumentIndexingService
    assert type(container.vector_index) is InMemoryVectorIndex
    assert type(container.lexical_index) is InMemoryBM25Index
    assert container.query_engine is None


def test_default_askme_service_is_safely_unavailable() -> None:
    container = create_application_container()

    with pytest.raises(AskMeUnavailableError) as exc_info:
        container.askme_service.ask(AskMeRequest(QUESTION))

    assert str(exc_info.value) == "AskMe is temporarily unavailable."


def test_composition_uses_supplied_askme_service_once() -> None:
    service = _askme_service()
    calls = 0

    def factory() -> AskMeService:
        nonlocal calls
        calls += 1
        return service

    container = create_application_container(
        factories=CompositionFactories(askme_service_factory=factory)
    )

    assert calls == 1
    assert container.askme_service is service


def test_composition_rejects_invalid_factory_result() -> None:
    def factory() -> AskMeService:
        return object()  # type: ignore[return-value]

    with pytest.raises(TypeError, match="AskMeService"):
        create_application_container(
            factories=CompositionFactories(askme_service_factory=factory)
        )


def test_expected_unavailable_factory_degrades_to_safe_default() -> None:
    def factory() -> AskMeService:
        raise AskMeUnavailableError("missing runtime configuration")

    container = create_application_container(
        factories=CompositionFactories(askme_service_factory=factory)
    )

    with pytest.raises(AskMeUnavailableError) as exc_info:
        container.askme_service.ask(AskMeRequest(QUESTION))

    assert "missing runtime configuration" not in str(exc_info.value)


def test_unexpected_factory_failure_is_not_hidden() -> None:
    def factory() -> AskMeService:
        raise RuntimeError("programming error")

    with pytest.raises(RuntimeError, match="programming error"):
        create_application_container(
            factories=CompositionFactories(askme_service_factory=factory)
        )


def test_separate_containers_do_not_share_catalog_state() -> None:
    first = create_application_container()
    second = create_application_container()

    first.catalog_service.register_upload(
        document_id=DOCUMENT_ID,
        filename="policy.pdf",
        uploaded_at=UPLOADED_AT,
        page_count=2,
    )

    assert len(first.catalog_service.list()) == 1
    assert second.catalog_service.list() == ()


def test_create_app_stores_container_on_state_and_reuses_services() -> None:
    container = _container()
    factory = CountingContainerFactory(container)
    application = create_app(container_factory=factory)

    with TestClient(application) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/admin/documents").json() == {"documents": []}
        client.post(
            "/admin/documents",
            json={"filename": "policy.pdf", "page_count": 2, "chunk_count": 0},
        )
        assert len(client.get("/admin/documents").json()["documents"]) == 1
        assert client.app.state.container is container

    assert factory.calls == 1


def test_create_app_instances_are_isolated() -> None:
    first = create_app(container_factory=create_application_container)
    second = create_app(container_factory=create_application_container)

    with TestClient(first) as first_client:
        first_client.post(
            "/admin/documents",
            json={"filename": "policy.pdf", "page_count": 2, "chunk_count": 0},
        )
        assert len(first_client.get("/admin/documents").json()["documents"]) == 1

    with TestClient(second) as second_client:
        assert second_client.get("/admin/documents").json() == {"documents": []}


def test_default_app_ask_route_remains_unavailable() -> None:
    application = create_app()

    with TestClient(application) as client:
        response = client.post("/ask", json={"question": QUESTION})

    assert response.status_code == 503
    assert response.json() == {"detail": "AskMe is temporarily unavailable."}


def test_injected_askme_service_can_answer_through_api() -> None:
    engine = FakeEngine(_validated_answer())
    service = AskMeService(query_engine=engine, request_id_factory=lambda: REQUEST_ID)
    container = _container(askme_service=service)
    application = create_app(container_factory=lambda: container)

    with TestClient(application) as client:
        response = client.post("/ask", json={"question": QUESTION})

    assert response.status_code == 200
    assert response.json()["answer"] == ANSWER
    assert response.json()["request_id"] == str(REQUEST_ID)
    assert engine.questions == [QUESTION]


def test_missing_application_container_fails_safely() -> None:
    application = create_app()

    with TestClient(application) as client:
        delattr(client.app.state, "container")
        response = client.get("/admin/documents")

    assert response.status_code == 503
    assert response.json() == {"detail": "Application services are unavailable."}


def test_dependency_overrides_do_not_leak_between_apps() -> None:
    first = create_app(
        container_factory=lambda: _container(askme_service=_askme_service())
    )
    second = create_app()

    with TestClient(first) as first_client:
        assert first_client.post("/ask", json={"question": QUESTION}).status_code == 200

    with TestClient(second) as second_client:
        assert (
            second_client.post("/ask", json={"question": QUESTION}).status_code == 503
        )


def test_application_composition_does_not_import_provider_or_model_loading_code() -> (
    None
):
    source = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "src/loreforge/application/__init__.py",
            "src/loreforge/application/container.py",
            "src/loreforge/application/composition.py",
        )
    )

    disallowed = (
        "OpenRouter",
        "LocalEmbedding",
        "LocalReranker",
        "SentenceTransformer",
        "CrossEncoder",
        "os.environ",
        "FastAPI",
        "Request",
        "Pydantic",
    )
    assert not any(term in source for term in disallowed)


def _container(
    *,
    askme_service: AskMeService | None = None,
) -> ApplicationContainer:
    catalog_service = CatalogService(InMemoryCatalogRepository())
    vector_index = InMemoryVectorIndex()
    lexical_index = InMemoryBM25Index()
    return ApplicationContainer(
        catalog_service=catalog_service,
        askme_service=askme_service or _askme_service(),
        document_indexing_service=_indexing_service(
            catalog_service,
            vector_index,
            lexical_index,
        ),
        vector_index=vector_index,
        lexical_index=lexical_index,
        query_engine=None,
    )


def _askme_service() -> AskMeService:
    return AskMeService(
        query_engine=FakeEngine(_validated_answer()),
        request_id_factory=lambda: REQUEST_ID,
    )


def _validated_answer() -> ValidatedGroundedAnswer:
    source = SourceReference(
        citation_id="S1",
        document_id=DOCUMENT_ID,
        chunk_id=CHUNK_ID,
        filename="refund-policy.pdf",
        page_number=2,
    )
    evidence_item = EvidenceItem(
        citation_id="S1",
        chunk_id=CHUNK_ID,
        document_id=DOCUMENT_ID,
        filename="refund-policy.pdf",
        page_number=2,
        text="Refund requests must be submitted within 14 days.",
        reranker_score=1.0,
        retrieval_rank=1,
    )
    rendered_text = (
        "[S1]\nSource: refund-policy.pdf\nPage: 2\nContent:\n"
        "Refund requests must be submitted within 14 days."
    )
    grounded_answer = GroundedAnswer(
        question=QUESTION,
        answer_text=ANSWER,
        sources=(source,),
        evidence=EvidenceContext(
            items=(evidence_item,),
            rendered_text=rendered_text,
            total_characters=len(rendered_text),
            truncated=False,
        ),
        provider_model="offline-test-model",
        finish_reason="stop",
        citations_validated=True,
    )
    return ValidatedGroundedAnswer(
        grounded_answer=grounded_answer,
        citation_validation=CitationValidationResult(
            citation_ids=("S1",),
            supported_citation_ids=("S1",),
            unsupported_citation_ids=(),
            missing_citations=False,
            is_valid=True,
        ),
        cited_sources=(source,),
    )


def test_composition_uses_supplied_indexing_service_once() -> None:
    calls = 0

    def factory(
        catalog_service: CatalogService,
        vector_index: InMemoryVectorIndex,
        lexical_index: InMemoryBM25Index,
    ) -> DocumentIndexingService:
        nonlocal calls
        calls += 1
        return _indexing_service(catalog_service, vector_index, lexical_index)

    container = create_application_container(
        factories=CompositionFactories(document_indexing_service_factory=factory)
    )

    assert calls == 1
    assert type(container.document_indexing_service) is DocumentIndexingService


def test_composition_rejects_invalid_indexing_service_factory_result() -> None:
    def factory(
        catalog_service: CatalogService,
        vector_index: InMemoryVectorIndex,
        lexical_index: InMemoryBM25Index,
    ) -> DocumentIndexingService:
        return object()  # type: ignore[return-value]

    with pytest.raises(TypeError, match="DocumentIndexingService"):
        create_application_container(
            factories=CompositionFactories(document_indexing_service_factory=factory)
        )


def test_indexing_service_reused_for_app_lifetime() -> None:
    container = create_application_container()
    application = create_app(container_factory=lambda: container)

    with TestClient(application) as client:
        first = client.app.state.container.document_indexing_service
        second = client.app.state.container.document_indexing_service

    assert first is second is container.document_indexing_service


def test_configured_runtime_creates_one_query_engine_and_askme_service() -> None:
    providers = RuntimeProviders()
    container = create_application_container(factories=_runtime_factories(providers))

    assert type(container.query_engine) is ProductionGroundedQueryEngine
    assert type(container.askme_service) is AskMeService
    assert container.askme_service._query_engine is container.query_engine
    assert providers.query_embedder_calls == 1
    assert providers.reranker_calls == 1
    assert providers.llm_calls == 1


def test_configured_runtime_reuses_shared_indexes_for_indexing_and_query() -> None:
    container = create_application_container(factories=_runtime_factories())

    assert container.document_indexing_service._vector_index is container.vector_index
    assert container.document_indexing_service._lexical_index is container.lexical_index
    assert container.query_engine._semantic_retriever is container.vector_index
    assert container.query_engine._lexical_retriever is container.lexical_index


def test_configured_askme_route_uses_shared_index_state() -> None:
    container = create_application_container(factories=_runtime_factories())
    _add_runtime_chunk(container)
    application = create_app(container_factory=lambda: container)

    with TestClient(application) as client:
        response = client.post("/ask", json={"question": QUESTION})

    assert response.status_code == 200
    body = response.json()
    assert body["question"] == QUESTION
    assert body["answer"] == ANSWER
    assert [citation["citation_id"] for citation in body["citations"]] == ["S1"]
    assert body["citations"][0]["chunk_id"] == str(CHUNK_ID)


def test_runtime_application_instances_have_isolated_indexes_and_engines() -> None:
    first = create_application_container(factories=_runtime_factories())
    second = create_application_container(factories=_runtime_factories())

    _add_runtime_chunk(first)

    assert first.query_engine is not second.query_engine
    assert first.askme_service is not second.askme_service
    assert first.vector_index is not second.vector_index
    assert first.lexical_index is not second.lexical_index
    assert first.vector_index.get(CHUNK_ID) is not None
    assert second.vector_index.get(CHUNK_ID) is None
    assert second.lexical_index.get(CHUNK_ID) is None


def test_partial_provider_configuration_keeps_askme_degraded() -> None:
    container = create_application_container(
        factories=CompositionFactories(
            query_embedding_provider_factory=lambda: FakeQueryEmbeddingProvider()
        )
    )

    assert container.query_engine is None
    with pytest.raises(AskMeUnavailableError):
        container.askme_service.ask(AskMeRequest(QUESTION))


class RuntimeProviders:
    def __init__(self) -> None:
        self.query_embedder = FakeQueryEmbeddingProvider()
        self.reranker = FakeRerankerProvider()
        self.llm = FakeLLMProvider()
        self.query_embedder_calls = 0
        self.reranker_calls = 0
        self.llm_calls = 0

    def query_embedder_factory(self) -> FakeQueryEmbeddingProvider:
        self.query_embedder_calls += 1
        return self.query_embedder

    def reranker_factory(self) -> FakeRerankerProvider:
        self.reranker_calls += 1
        return self.reranker

    def llm_factory(self) -> FakeLLMProvider:
        self.llm_calls += 1
        return self.llm


class FakeQueryEmbeddingProvider:
    def embed_documents(
        self,
        requests: tuple[EmbeddingRequest, ...],
    ) -> EmbeddingResult:
        return EmbeddingResult(
            model="fake-query",
            dimensions=2,
            vectors=tuple(
                EmbeddingVector(item_id=request.item_id, values=(1.0, 0.0))
                for request in requests
            ),
        )

    def embed_query(self, question: str) -> EmbeddingVector:
        return EmbeddingVector(item_id=CHUNK_ID, values=(1.0, 0.0))


class FakeRerankerProvider:
    def score(
        self,
        requests: tuple[RerankingRequest, ...],
    ) -> tuple[RerankingScore, ...]:
        return tuple(
            RerankingScore(item_id=request.item_id, score=1.0) for request in requests
        )


class FakeLLMProvider:
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        return GenerationResponse(
            text=ANSWER,
            model="fake-llm",
            finish_reason="stop",
        )


def _runtime_factories(
    providers: RuntimeProviders | None = None,
) -> CompositionFactories:
    runtime = providers or RuntimeProviders()
    return CompositionFactories(
        query_embedding_provider_factory=runtime.query_embedder_factory,
        reranker_provider_factory=runtime.reranker_factory,
        llm_provider_factory=runtime.llm_factory,
    )


def _add_runtime_chunk(container: ApplicationContainer) -> None:
    source = DocumentSource(
        filename="refund-policy.pdf",
        media_type="application/pdf",
        size_bytes=100,
    )
    chunk = DocumentChunk(
        chunk_id=CHUNK_ID,
        document_id=DOCUMENT_ID,
        source=source,
        page_number=2,
        chunk_index=0,
        text="Refund policy requests must be submitted within 14 days.",
    )
    vector = EmbeddingVector(item_id=CHUNK_ID, values=(1.0, 0.0))
    container.vector_index.add((EmbeddedChunk(chunk=chunk, vector=vector),))
    container.lexical_index.add((chunk,))


def _indexing_service(
    catalog_service: CatalogService,
    vector_index: InMemoryVectorIndex,
    lexical_index: InMemoryBM25Index,
) -> DocumentIndexingService:
    return DocumentIndexingService(
        catalog_service=catalog_service,
        embedding_provider=None,
        vector_index=vector_index,
        lexical_index=lexical_index,
    )
