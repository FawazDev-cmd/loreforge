from dataclasses import FrozenInstanceError
from math import inf, nan
from uuid import uuid4

import pytest

from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.embeddings import EmbeddingVector
from loreforge.vector_index import IndexedVector, VectorSearchResult


def test_indexed_vector_accepts_matching_chunk_and_vector_id() -> None:
    chunk = _chunk()
    vector = EmbeddingVector(item_id=chunk.chunk_id, values=(0.1, 0.2))

    indexed = IndexedVector(chunk=chunk, vector=vector)

    assert indexed.chunk == chunk
    assert indexed.vector == vector


def test_indexed_vector_rejects_mismatched_chunk_and_vector_id() -> None:
    with pytest.raises(ValueError, match="item_id"):
        IndexedVector(
            chunk=_chunk(),
            vector=EmbeddingVector(item_id=uuid4(), values=(0.1,)),
        )


def test_indexed_vector_is_immutable() -> None:
    chunk = _chunk()
    indexed = IndexedVector(
        chunk=chunk,
        vector=EmbeddingVector(item_id=chunk.chunk_id, values=(0.1,)),
    )

    with pytest.raises(FrozenInstanceError):
        indexed.chunk = _chunk()


def test_vector_search_result_accepts_valid_values() -> None:
    indexed = _indexed_vector()

    result = VectorSearchResult(indexed=indexed, score=0.5, rank=1)

    assert result.indexed == indexed
    assert result.score == 0.5
    assert result.rank == 1


def test_vector_search_result_rejects_integer_score() -> None:
    with pytest.raises(ValueError, match="score"):
        VectorSearchResult(indexed=_indexed_vector(), score=1, rank=1)  # type: ignore[arg-type]


def test_vector_search_result_rejects_boolean_score() -> None:
    with pytest.raises(ValueError, match="score"):
        VectorSearchResult(indexed=_indexed_vector(), score=True, rank=1)  # type: ignore[arg-type]


@pytest.mark.parametrize("score", [nan, inf, -inf])
def test_vector_search_result_rejects_non_finite_score(score: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        VectorSearchResult(indexed=_indexed_vector(), score=score, rank=1)


def test_vector_search_result_rejects_rank_below_one() -> None:
    with pytest.raises(ValueError, match="rank"):
        VectorSearchResult(indexed=_indexed_vector(), score=0.5, rank=0)


def test_vector_search_result_is_immutable() -> None:
    result = VectorSearchResult(indexed=_indexed_vector(), score=0.5, rank=1)

    with pytest.raises(FrozenInstanceError):
        result.rank = 2


def _indexed_vector() -> IndexedVector:
    chunk = _chunk()
    return IndexedVector(
        chunk=chunk,
        vector=EmbeddingVector(item_id=chunk.chunk_id, values=(0.1,)),
    )


def _source() -> DocumentSource:
    return DocumentSource(
        filename="sample.pdf",
        media_type="application/pdf",
        size_bytes=128,
    )


def _chunk() -> DocumentChunk:
    return DocumentChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        source=_source(),
        page_number=1,
        chunk_index=0,
        text="Chunk text",
    )
