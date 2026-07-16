"""Deterministic exact in-memory vector index."""

from uuid import UUID

from loreforge.embeddings.pipeline import EmbeddedChunk
from loreforge.vector_index.models import IndexedVector, VectorSearchResult
from loreforge.vector_index.similarity import SimilarityError, cosine_similarity


class VectorIndexError(ValueError):
    """Raised when vector-index contract validation fails."""


class InMemoryVectorIndex:
    """Exact in-memory index for embedded document chunks."""

    def __init__(self) -> None:
        self._items: dict[UUID, IndexedVector] = {}
        self._dimensions: int | None = None

    @property
    def dimensions(self) -> int | None:
        """Return the established vector dimension, if any."""
        return self._dimensions

    @property
    def size(self) -> int:
        """Return the number of indexed vectors."""
        return len(self._items)

    def add(self, items: tuple[EmbeddedChunk, ...]) -> None:
        """Atomically add embedded chunks to the index."""
        if not items:
            msg = "items must contain at least one embedded chunk"
            raise VectorIndexError(msg)

        indexed_items = tuple(
            IndexedVector(chunk=item.chunk, vector=item.vector) for item in items
        )
        self._validate_new_items(indexed_items)

        for indexed in indexed_items:
            self._items[indexed.chunk.chunk_id] = indexed

        if self._dimensions is None:
            self._dimensions = len(indexed_items[0].vector.values)

    def get(self, chunk_id: UUID) -> IndexedVector | None:
        """Return an indexed vector by chunk ID when present."""
        return self._items.get(chunk_id)

    def remove(self, chunk_id: UUID) -> bool:
        """Remove an indexed vector by chunk ID."""
        if chunk_id not in self._items:
            return False

        del self._items[chunk_id]
        if not self._items:
            self._dimensions = None

        return True

    def search(
        self,
        *,
        query_vector: tuple[float, ...],
        top_k: int,
    ) -> tuple[VectorSearchResult, ...]:
        """Search indexed vectors by exact cosine similarity."""
        if top_k <= 0:
            msg = "top_k must be greater than zero"
            raise VectorIndexError(msg)

        if not self._items or self._dimensions is None:
            msg = "cannot search an empty vector index"
            raise VectorIndexError(msg)

        if len(query_vector) != self._dimensions:
            msg = "query vector dimensions must match index dimensions"
            raise VectorIndexError(msg)

        try:
            scored = tuple(
                (indexed, cosine_similarity(query_vector, indexed.vector.values))
                for indexed in self._items.values()
            )
        except SimilarityError as error:
            msg = "query vector is invalid"
            raise VectorIndexError(msg) from error

        ranked = sorted(
            scored,
            key=lambda item: (-item[1], str(item[0].chunk.chunk_id)),
        )[:top_k]

        return tuple(
            VectorSearchResult(indexed=indexed, score=score, rank=rank)
            for rank, (indexed, score) in enumerate(ranked, start=1)
        )

    def _validate_new_items(self, items: tuple[IndexedVector, ...]) -> None:
        item_ids = tuple(item.chunk.chunk_id for item in items)
        if len(set(item_ids)) != len(item_ids):
            msg = "batch contains duplicate chunk IDs"
            raise VectorIndexError(msg)

        existing_ids = set(self._items)
        if any(item_id in existing_ids for item_id in item_ids):
            msg = "chunk ID already exists in index"
            raise VectorIndexError(msg)

        expected_dimensions = self._dimensions or len(items[0].vector.values)
        for item in items:
            if len(item.vector.values) != expected_dimensions:
                msg = "vector dimensions must match index dimensions"
                raise VectorIndexError(msg)
