"""Shared application service container."""

from dataclasses import dataclass, field

from loreforge.askme import AskMeService
from loreforge.auth import (
    Authenticator,
    DisabledAuthenticator,
    InMemoryUserRepository,
    UserRepository,
)
from loreforge.catalog import CatalogService
from loreforge.database import DatabaseRuntime
from loreforge.indexing import DocumentIndexingService
from loreforge.observability import (
    InMemoryMetricsRecorder,
    InMemoryOperationalMetricsRecorder,
)
from loreforge.query import ProductionGroundedQueryEngine
from loreforge.retrieval.bm25 import InMemoryBM25Index
from loreforge.settings import LoreForgeSettings
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
    operational_metrics: InMemoryOperationalMetricsRecorder = field(
        default_factory=InMemoryOperationalMetricsRecorder
    )
    authenticator: Authenticator = field(default_factory=DisabledAuthenticator)
    user_repository: UserRepository = field(default_factory=InMemoryUserRepository)
    settings: LoreForgeSettings = field(default_factory=LoreForgeSettings)
    database: DatabaseRuntime | None = None

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
        if type(self.operational_metrics) is not InMemoryOperationalMetricsRecorder:
            msg = "operational_metrics must be an InMemoryOperationalMetricsRecorder"
            raise TypeError(msg)
        if type(self.settings) is not LoreForgeSettings:
            msg = "settings must be LoreForgeSettings"
            raise TypeError(msg)
        if self.database is not None and type(self.database) is not DatabaseRuntime:
            msg = "database must be a DatabaseRuntime or None"
            raise TypeError(msg)

    def close(self) -> None:
        """Release owned runtime resources."""
        if self.database is not None:
            self.database.close()
