"""SQLAlchemy-backed persistence adapters for LoreForge."""

from loreforge.database.auth import SqlAlchemyUserRepository
from loreforge.database.catalog import SqlAlchemyCatalogRepository
from loreforge.database.engine import (
    DatabaseHealth,
    DatabaseRuntime,
    check_database_health,
    create_database_runtime,
    create_sqlalchemy_engine,
    normalize_database_url,
    run_migrations,
)
from loreforge.database.indexing import SqlAlchemyIndexingStateRepository
from loreforge.database.retrieval import (
    SqlAlchemyChunkRepository,
    SqlAlchemyEmbeddingRepository,
    SqlAlchemyRetrievalRepository,
)

__all__ = [
    "DatabaseHealth",
    "DatabaseRuntime",
    "SqlAlchemyCatalogRepository",
    "SqlAlchemyChunkRepository",
    "SqlAlchemyEmbeddingRepository",
    "SqlAlchemyIndexingStateRepository",
    "SqlAlchemyRetrievalRepository",
    "SqlAlchemyUserRepository",
    "check_database_health",
    "create_database_runtime",
    "create_sqlalchemy_engine",
    "normalize_database_url",
    "run_migrations",
]
