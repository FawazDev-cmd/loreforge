from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import UUID

import pytest

from loreforge.application import ApplicationContainer
from loreforge.askme import AskMeService
from loreforge.catalog import CatalogService, InMemoryCatalogRepository
from loreforge.generation.validation_models import ValidatedGroundedAnswer
from loreforge.indexing import DocumentIndexingService
from loreforge.observability import InMemoryMetricsRecorder
from loreforge.retrieval.bm25 import InMemoryBM25Index
from loreforge.vector_index import InMemoryVectorIndex

DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000001")


class UnavailableEngine:
    def answer(self, question: str) -> ValidatedGroundedAnswer:
        raise RuntimeError("not used")


def test_container_requires_exact_catalog_service() -> None:
    services = _services()

    with pytest.raises(TypeError, match="CatalogService"):
        ApplicationContainer(  # type: ignore[arg-type]
            catalog_service=object(),
            askme_service=services.askme_service,
            document_indexing_service=services.indexing_service,
            vector_index=services.vector_index,
            lexical_index=services.lexical_index,
            query_engine=None,
            metrics_recorder=services.metrics_recorder,
        )


def test_container_requires_exact_askme_service() -> None:
    services = _services()

    with pytest.raises(TypeError, match="AskMeService"):
        ApplicationContainer(  # type: ignore[arg-type]
            catalog_service=services.catalog_service,
            askme_service=object(),
            document_indexing_service=services.indexing_service,
            vector_index=services.vector_index,
            lexical_index=services.lexical_index,
            query_engine=None,
            metrics_recorder=services.metrics_recorder,
        )


def test_container_requires_exact_document_indexing_service() -> None:
    services = _services()

    with pytest.raises(TypeError, match="DocumentIndexingService"):
        ApplicationContainer(  # type: ignore[arg-type]
            catalog_service=services.catalog_service,
            askme_service=services.askme_service,
            document_indexing_service=object(),
            vector_index=services.vector_index,
            lexical_index=services.lexical_index,
            query_engine=None,
            metrics_recorder=services.metrics_recorder,
        )


def test_container_requires_exact_vector_index() -> None:
    services = _services()

    with pytest.raises(TypeError, match="InMemoryVectorIndex"):
        ApplicationContainer(  # type: ignore[arg-type]
            catalog_service=services.catalog_service,
            askme_service=services.askme_service,
            document_indexing_service=services.indexing_service,
            vector_index=object(),
            lexical_index=services.lexical_index,
            query_engine=None,
            metrics_recorder=services.metrics_recorder,
        )


def test_container_requires_exact_lexical_index() -> None:
    services = _services()

    with pytest.raises(TypeError, match="InMemoryBM25Index"):
        ApplicationContainer(  # type: ignore[arg-type]
            catalog_service=services.catalog_service,
            askme_service=services.askme_service,
            document_indexing_service=services.indexing_service,
            vector_index=services.vector_index,
            lexical_index=object(),
            query_engine=None,
            metrics_recorder=services.metrics_recorder,
        )


def test_container_rejects_invalid_query_engine() -> None:
    services = _services()

    with pytest.raises(TypeError, match="ProductionGroundedQueryEngine"):
        ApplicationContainer(  # type: ignore[arg-type]
            catalog_service=services.catalog_service,
            askme_service=services.askme_service,
            document_indexing_service=services.indexing_service,
            vector_index=services.vector_index,
            lexical_index=services.lexical_index,
            query_engine=object(),
            metrics_recorder=services.metrics_recorder,
        )


def test_container_rejects_invalid_metrics_recorder() -> None:
    services = _services()

    with pytest.raises(TypeError, match="InMemoryMetricsRecorder"):
        ApplicationContainer(  # type: ignore[arg-type]
            catalog_service=services.catalog_service,
            askme_service=services.askme_service,
            document_indexing_service=services.indexing_service,
            vector_index=services.vector_index,
            lexical_index=services.lexical_index,
            query_engine=None,
            metrics_recorder=object(),
        )


def test_container_is_immutable() -> None:
    container = _container()

    with pytest.raises(FrozenInstanceError):
        container.catalog_service = CatalogService(  # type: ignore[misc]
            InMemoryCatalogRepository()
        )


def test_container_retains_service_identity() -> None:
    services = _services()

    container = ApplicationContainer(
        catalog_service=services.catalog_service,
        askme_service=services.askme_service,
        document_indexing_service=services.indexing_service,
        vector_index=services.vector_index,
        lexical_index=services.lexical_index,
        query_engine=None,
        metrics_recorder=services.metrics_recorder,
    )

    assert container.catalog_service is services.catalog_service
    assert container.askme_service is services.askme_service
    assert container.document_indexing_service is services.indexing_service
    assert container.vector_index is services.vector_index
    assert container.lexical_index is services.lexical_index
    assert container.query_engine is None
    assert container.metrics_recorder is services.metrics_recorder


def test_container_has_no_fastapi_or_pydantic_imports() -> None:
    source = Path("src/loreforge/application/container.py").read_text(encoding="utf-8")

    assert "fastapi" not in source.lower()
    assert "starlette" not in source.lower()
    assert "pydantic" not in source.lower()


class Services:
    def __init__(self) -> None:
        self.catalog_service = CatalogService(InMemoryCatalogRepository())
        self.askme_service = AskMeService(query_engine=UnavailableEngine())
        self.vector_index = InMemoryVectorIndex()
        self.lexical_index = InMemoryBM25Index()
        self.metrics_recorder = InMemoryMetricsRecorder()
        self.indexing_service = DocumentIndexingService(
            catalog_service=self.catalog_service,
            embedding_provider=None,
            vector_index=self.vector_index,
            lexical_index=self.lexical_index,
        )


def _container() -> ApplicationContainer:
    services = _services()
    return ApplicationContainer(
        catalog_service=services.catalog_service,
        askme_service=services.askme_service,
        document_indexing_service=services.indexing_service,
        vector_index=services.vector_index,
        lexical_index=services.lexical_index,
        query_engine=None,
        metrics_recorder=services.metrics_recorder,
    )


def _services() -> Services:
    return Services()
