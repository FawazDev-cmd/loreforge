"""Public embedding contracts for LoreForge."""

from loreforge.embeddings.local import (
    LocalEmbeddingError,
    LocalSentenceTransformerProvider,
)
from loreforge.embeddings.models import (
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingVector,
)
from loreforge.embeddings.pipeline import (
    EmbeddedChunk,
    EmbeddingPipelineError,
    embed_chunks,
)
from loreforge.embeddings.provider import EmbeddingProvider

__all__ = [
    "EmbeddedChunk",
    "EmbeddingProvider",
    "EmbeddingPipelineError",
    "EmbeddingRequest",
    "EmbeddingResult",
    "EmbeddingVector",
    "LocalEmbeddingError",
    "LocalSentenceTransformerProvider",
    "embed_chunks",
]
