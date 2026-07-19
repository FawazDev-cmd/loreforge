"""Document indexing public surface."""

from loreforge.indexing.errors import (
    DocumentAlreadyIndexedError,
    DocumentIndexingError,
    DocumentIndexingExecutionError,
)
from loreforge.indexing.models import IndexedDocumentResult
from loreforge.indexing.service import DocumentIndexingService, PdfIngestor
from loreforge.indexing.state import (
    IndexingState,
    IndexingStateRepository,
    IndexingStateRepositoryError,
    IndexingStatus,
    InMemoryIndexingStateRepository,
)

__all__ = [
    "DocumentAlreadyIndexedError",
    "DocumentIndexingError",
    "DocumentIndexingExecutionError",
    "DocumentIndexingService",
    "IndexedDocumentResult",
    "IndexingState",
    "IndexingStateRepository",
    "IndexingStateRepositoryError",
    "IndexingStatus",
    "InMemoryIndexingStateRepository",
    "PdfIngestor",
]
