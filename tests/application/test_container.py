from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import UUID

import pytest

from loreforge.application import ApplicationContainer
from loreforge.askme import AskMeService
from loreforge.catalog import CatalogService, InMemoryCatalogRepository
from loreforge.generation.validation_models import ValidatedGroundedAnswer
from loreforge.indexing import DocumentIndexingService
from loreforge.retrieval.bm25 import InMemoryBM25Index
from loreforge.vector_index import InMemoryVectorIndex

DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000001")


class UnavailableEngine:
    def answer(self, question: str) -> ValidatedGroundedAnswer:
        raise RuntimeError("not used")


def test_container_requires_exact_catalog_service() -> None:
    catalog_service = CatalogService(InMemoryCatalogRepository())
    askme_service = AskMeService(query_engine=UnavailableEngine())

    with pytest.raises(TypeError, match="CatalogService"):
        ApplicationContainer(  # type: ignore[arg-type]
            catalog_service=object(),
            askme_service=askme_service,
            document_indexing_service=_indexing_service(catalog_service),
        )


def test_container_requires_exact_askme_service() -> None:
    catalog_service = CatalogService(InMemoryCatalogRepository())

    with pytest.raises(TypeError, match="AskMeService"):
        ApplicationContainer(  # type: ignore[arg-type]
            catalog_service=catalog_service,
            askme_service=object(),
            document_indexing_service=_indexing_service(catalog_service),
        )


def test_container_requires_exact_document_indexing_service() -> None:
    catalog_service = CatalogService(InMemoryCatalogRepository())
    askme_service = AskMeService(query_engine=UnavailableEngine())

    with pytest.raises(TypeError, match="DocumentIndexingService"):
        ApplicationContainer(  # type: ignore[arg-type]
            catalog_service=catalog_service,
            askme_service=askme_service,
            document_indexing_service=object(),
        )


def test_container_is_immutable() -> None:
    container = _container()

    with pytest.raises(FrozenInstanceError):
        container.catalog_service = CatalogService(  # type: ignore[misc]
            InMemoryCatalogRepository()
        )


def test_container_retains_service_identity() -> None:
    catalog_service = CatalogService(InMemoryCatalogRepository())
    askme_service = AskMeService(query_engine=UnavailableEngine())
    indexing_service = _indexing_service(catalog_service)

    container = ApplicationContainer(
        catalog_service=catalog_service,
        askme_service=askme_service,
        document_indexing_service=indexing_service,
    )

    assert container.catalog_service is catalog_service
    assert container.askme_service is askme_service
    assert container.document_indexing_service is indexing_service


def test_container_has_no_fastapi_or_pydantic_imports() -> None:
    source = Path("src/loreforge/application/container.py").read_text(encoding="utf-8")

    assert "fastapi" not in source.lower()
    assert "starlette" not in source.lower()
    assert "pydantic" not in source.lower()


def _container() -> ApplicationContainer:
    catalog_service = CatalogService(InMemoryCatalogRepository())
    return ApplicationContainer(
        catalog_service=catalog_service,
        askme_service=AskMeService(query_engine=UnavailableEngine()),
        document_indexing_service=_indexing_service(catalog_service),
    )


def _indexing_service(catalog_service: CatalogService) -> DocumentIndexingService:
    return DocumentIndexingService(
        catalog_service=catalog_service,
        embedding_provider=None,
        vector_index=InMemoryVectorIndex(),
        lexical_index=InMemoryBM25Index(),
    )
