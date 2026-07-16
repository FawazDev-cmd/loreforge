"""Embedding provider protocol."""

from typing import Protocol, runtime_checkable

from loreforge.embeddings.models import (
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingVector,
)


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Replaceable provider that embeds ordered text requests."""

    def embed(
        self,
        requests: tuple[EmbeddingRequest, ...],
    ) -> EmbeddingResult:
        """Return embedding vectors for the supplied requests."""
        ...


@runtime_checkable
class QueryEmbeddingProvider(Protocol):
    """Provider that embeds document batches and user queries separately."""

    def embed_documents(
        self,
        requests: tuple[EmbeddingRequest, ...],
    ) -> EmbeddingResult:
        """Return embedding vectors for ordered document requests."""
        ...

    def embed_query(self, question: str) -> EmbeddingVector:
        """Return one embedding vector for a user query."""
        ...
