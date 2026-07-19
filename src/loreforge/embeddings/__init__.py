"""Public embedding contracts for LoreForge."""

from loreforge.embeddings.gemini import (
    GeminiEmbeddingConfig,
    GeminiEmbeddingError,
    GeminiEmbeddingProvider,
)
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
from loreforge.embeddings.provider import EmbeddingProvider, QueryEmbeddingProvider

__all__ = [
    "EmbeddedChunk",
    "EmbeddingProvider",
    "EmbeddingPipelineError",
    "EmbeddingRequest",
    "EmbeddingResult",
    "EmbeddingVector",
    "GeminiEmbeddingConfig",
    "GeminiEmbeddingError",
    "GeminiEmbeddingProvider",
    "LocalEmbeddingError",
    "LocalSentenceTransformerProvider",
    "QueryEmbeddingProvider",
    "embed_chunks",
]
