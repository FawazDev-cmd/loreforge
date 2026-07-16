"""Immutable vector-index domain models."""

from dataclasses import dataclass
from math import isfinite

from loreforge.documents.models import DocumentChunk
from loreforge.embeddings.models import EmbeddingVector


@dataclass(frozen=True, slots=True)
class IndexedVector:
    """Stored embedding vector with complete chunk provenance."""

    chunk: DocumentChunk
    vector: EmbeddingVector

    def __post_init__(self) -> None:
        if self.vector.item_id != self.chunk.chunk_id:
            msg = "vector item_id must match chunk chunk_id"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class VectorSearchResult:
    """Ranked vector-search hit with cosine similarity score."""

    indexed: IndexedVector
    score: float
    rank: int

    def __post_init__(self) -> None:
        if type(self.score) is not float:
            msg = "score must be a float"
            raise ValueError(msg)

        if not isfinite(self.score):
            msg = "score must be finite"
            raise ValueError(msg)

        if self.rank < 1:
            msg = "rank must be greater than or equal to 1"
            raise ValueError(msg)
