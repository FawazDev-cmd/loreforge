"""Embedding provider protocol."""

from typing import Protocol, runtime_checkable

from loreforge.embeddings.models import EmbeddingRequest, EmbeddingResult


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Replaceable provider that embeds ordered text requests."""

    def embed(
        self,
        requests: tuple[EmbeddingRequest, ...],
    ) -> EmbeddingResult:
        """Return embedding vectors for the supplied requests."""
        ...
