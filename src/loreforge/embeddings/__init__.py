"""Public embedding contracts for LoreForge."""

from loreforge.embeddings.models import (
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingVector,
)
from loreforge.embeddings.provider import EmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "EmbeddingRequest",
    "EmbeddingResult",
    "EmbeddingVector",
]
