"""Shared application service container."""

from dataclasses import dataclass

from loreforge.askme import AskMeService
from loreforge.catalog import CatalogService
from loreforge.indexing import DocumentIndexingService
from loreforge.observability import InMemoryMetricsRecorder
from loreforge.query import ProductionGroundedQueryEngine
from loreforge.retrieval.bm25 import InMemoryBM25Index
from loreforge.vector_index import InMemoryVectorIndex


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    """Immutable references to services owned by one application instance."""

    catalog_service: CatalogService
    askme_service: AskMeService
    document_indexing_service: DocumentIndexingService
    vector_index: InMemoryVectorIndex
    lexical_index: InMemoryBM25Index
    query_engine: ProductionGroundedQueryEngine | None
    metrics_recorder: InMemoryMetricsRecorder

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
        if type(self.vector_index) is not InMemoryVectorIndex:
            msg = "vector_index must be an InMemoryVectorIndex"
            raise TypeError(msg)
        if type(self.lexical_index) is not InMemoryBM25Index:
            msg = "lexical_index must be an InMemoryBM25Index"
            raise TypeError(msg)
        if (
            self.query_engine is not None
            and type(self.query_engine) is not ProductionGroundedQueryEngine
        ):
            msg = "query_engine must be a ProductionGroundedQueryEngine or None"
            raise TypeError(msg)
        if type(self.metrics_recorder) is not InMemoryMetricsRecorder:
            msg = "metrics_recorder must be an InMemoryMetricsRecorder"
            raise TypeError(msg)
