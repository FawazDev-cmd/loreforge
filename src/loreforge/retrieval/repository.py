"""Repository protocols for durable retrieval data."""

from typing import Protocol, runtime_checkable
from uuid import UUID

from loreforge.documents import DocumentChunk
from loreforge.embeddings.pipeline import EmbeddedChunk
from loreforge.retrieval.filters import RetrievalFilter
from loreforge.retrieval.lexical_models import (
    LexicalSearchRequest,
    LexicalSearchResponse,
)
from loreforge.vector_index import VectorSearchResult


class RetrievalRepositoryError(ValueError):
    """Raised when durable retrieval repository state would become invalid."""


@runtime_checkable
class ChunkRepository(Protocol):
    """Repository for citation-ready document chunks."""

    def add(
        self,
        chunks: tuple[DocumentChunk, ...],
        owner_user_id: UUID | None = None,
    ) -> None:
        """Persist ordered document chunks."""
        ...

    def get(self, chunk_id: UUID) -> DocumentChunk | None:
        """Return a chunk by ID when present."""
        ...

    def list(
        self,
        filters: RetrievalFilter = RetrievalFilter(),
    ) -> tuple[DocumentChunk, ...]:
        """Return chunks in insertion order, optionally filtered by metadata."""
        ...

    def list_for_document(self, document_id: UUID) -> tuple[DocumentChunk, ...]:
        """Return chunks for one document in insertion order."""
        ...

    def remove(self, chunk_id: UUID) -> bool:
        """Remove a chunk by ID."""
        ...


@runtime_checkable
class EmbeddingRepository(Protocol):
    """Repository for embedded chunks."""

    def add(self, embedded_chunks: tuple[EmbeddedChunk, ...]) -> None:
        """Persist ordered embedded chunks."""
        ...

    def get(self, chunk_id: UUID) -> EmbeddedChunk | None:
        """Return an embedded chunk by chunk ID when present."""
        ...

    def list(
        self,
        filters: RetrievalFilter = RetrievalFilter(),
    ) -> tuple[EmbeddedChunk, ...]:
        """Return embedded chunks in insertion order, optionally filtered."""
        ...

    def list_for_document(self, document_id: UUID) -> tuple[EmbeddedChunk, ...]:
        """Return embedded chunks for one document in insertion order."""
        ...

    def remove(self, chunk_id: UUID) -> bool:
        """Remove an embedding by chunk ID."""
        ...


@runtime_checkable
class RetrievalRepository(Protocol):
    """Repository-backed lexical and vector retrieval boundary."""

    def lexical_search(
        self,
        request: LexicalSearchRequest,
        filters: RetrievalFilter = RetrievalFilter(),
    ) -> LexicalSearchResponse:
        """Search persisted chunks with lexical retrieval."""
        ...

    def vector_search(
        self,
        *,
        query_vector: tuple[float, ...],
        top_k: int,
        filters: RetrievalFilter = RetrievalFilter(),
    ) -> tuple[VectorSearchResult, ...]:
        """Search persisted embeddings with vector retrieval."""
        ...
