"""Exact in-memory vector indexing primitives."""

from loreforge.vector_index.memory import InMemoryVectorIndex, VectorIndexError
from loreforge.vector_index.models import IndexedVector, VectorSearchResult
from loreforge.vector_index.similarity import SimilarityError, cosine_similarity

__all__ = [
    "InMemoryVectorIndex",
    "IndexedVector",
    "SimilarityError",
    "VectorIndexError",
    "VectorSearchResult",
    "cosine_similarity",
]
