from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

import pytest

from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.embeddings import (
    EmbeddedChunk,
    EmbeddingPipelineError,
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingVector,
    embed_chunks,
)


class DeterministicProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[EmbeddingRequest, ...]] = []

    def embed(self, requests: tuple[EmbeddingRequest, ...]) -> EmbeddingResult:
        self.calls.append(requests)
        vectors = tuple(
            EmbeddingVector(
                item_id=request.item_id,
                values=(float(index), float(len(request.text))),
            )
            for index, request in enumerate(requests, start=1)
        )
        return EmbeddingResult(
            model="deterministic-test-model",
            dimensions=2,
            vectors=vectors,
        )


class StaticProvider:
    def __init__(self, result: EmbeddingResult) -> None:
        self.result = result
        self.calls: list[tuple[EmbeddingRequest, ...]] = []

    def embed(self, requests: tuple[EmbeddingRequest, ...]) -> EmbeddingResult:
        self.calls.append(requests)
        return self.result


def test_embed_chunks_maps_one_chunk_to_one_embedded_chunk() -> None:
    chunk = _chunk(text="Single chunk")
    provider = DeterministicProvider()

    result = embed_chunks(chunks=(chunk,), provider=provider)

    assert len(result) == 1
    assert result[0].chunk == chunk
    assert result[0].vector.item_id == chunk.chunk_id
    assert result[0].vector.values == (1.0, 12.0)


def test_embed_chunks_preserves_multiple_chunk_order() -> None:
    chunks = (
        _chunk(text="First chunk", chunk_index=0),
        _chunk(text="Second chunk", chunk_index=1),
        _chunk(text="Third chunk", chunk_index=2),
    )

    result = embed_chunks(chunks=chunks, provider=DeterministicProvider())

    assert [embedded.chunk for embedded in result] == list(chunks)
    assert [embedded.vector.item_id for embedded in result] == [
        chunk.chunk_id for chunk in chunks
    ]


def test_embed_chunks_uses_chunk_ids_as_request_item_ids() -> None:
    chunks = (
        _chunk(text="First chunk", chunk_index=0),
        _chunk(text="Second chunk", chunk_index=1),
    )
    provider = DeterministicProvider()

    embed_chunks(chunks=chunks, provider=provider)

    assert len(provider.calls) == 1
    assert [request.item_id for request in provider.calls[0]] == [
        chunk.chunk_id for chunk in chunks
    ]
    assert [request.text for request in provider.calls[0]] == [
        chunk.text for chunk in chunks
    ]


def test_embed_chunks_calls_provider_exactly_once() -> None:
    provider = DeterministicProvider()

    embed_chunks(chunks=(_chunk(), _chunk(chunk_index=1)), provider=provider)

    assert len(provider.calls) == 1


def test_embed_chunks_returns_immutable_tuple() -> None:
    result = embed_chunks(chunks=(_chunk(),), provider=DeterministicProvider())

    assert isinstance(result, tuple)
    with pytest.raises(AttributeError):
        result.append(result[0])  # type: ignore[attr-defined]


def test_embed_chunks_does_not_mutate_input_chunks() -> None:
    chunks = (_chunk(text="Stable chunk"),)
    before = chunks

    embed_chunks(chunks=chunks, provider=DeterministicProvider())

    assert chunks == before


def test_embed_chunks_is_deterministic_with_deterministic_provider() -> None:
    chunks = (
        _chunk(text="First chunk", chunk_index=0),
        _chunk(text="Second chunk", chunk_index=1),
    )

    first = embed_chunks(chunks=chunks, provider=DeterministicProvider())
    second = embed_chunks(chunks=chunks, provider=DeterministicProvider())

    assert first == second


def test_embedded_chunk_accepts_matching_identity() -> None:
    chunk = _chunk()
    vector = EmbeddingVector(item_id=chunk.chunk_id, values=(0.1,))

    embedded = EmbeddedChunk(chunk=chunk, vector=vector)

    assert embedded.chunk == chunk
    assert embedded.vector == vector


def test_embedded_chunk_rejects_mismatched_identity() -> None:
    with pytest.raises(ValueError, match="item_id"):
        EmbeddedChunk(
            chunk=_chunk(),
            vector=EmbeddingVector(item_id=uuid4(), values=(0.1,)),
        )


def test_embedded_chunk_is_immutable() -> None:
    chunk = _chunk()
    embedded = EmbeddedChunk(
        chunk=chunk,
        vector=EmbeddingVector(item_id=chunk.chunk_id, values=(0.1,)),
    )

    with pytest.raises(FrozenInstanceError):
        embedded.chunk = _chunk()


def test_embed_chunks_rejects_empty_chunk_tuple() -> None:
    with pytest.raises(ValueError, match="chunks"):
        embed_chunks(chunks=(), provider=DeterministicProvider())


def test_embed_chunks_rejects_missing_vector() -> None:
    chunks = (_chunk(chunk_index=0), _chunk(chunk_index=1))
    result = _result_for_ids((chunks[0].chunk_id,))

    with pytest.raises(EmbeddingPipelineError, match="number"):
        embed_chunks(chunks=chunks, provider=StaticProvider(result))


def test_embed_chunks_rejects_extra_vector() -> None:
    chunk = _chunk()
    result = _result_for_ids((chunk.chunk_id, uuid4()))

    with pytest.raises(EmbeddingPipelineError, match="number"):
        embed_chunks(chunks=(chunk,), provider=StaticProvider(result))


def test_embed_chunks_rejects_reordered_vectors() -> None:
    chunks = (_chunk(chunk_index=0), _chunk(chunk_index=1))
    result = _result_for_ids((chunks[1].chunk_id, chunks[0].chunk_id))

    with pytest.raises(EmbeddingPipelineError, match="order"):
        embed_chunks(chunks=chunks, provider=StaticProvider(result))


def test_embed_chunks_rejects_mismatched_item_id() -> None:
    chunk = _chunk()
    result = _result_for_ids((uuid4(),))

    with pytest.raises(EmbeddingPipelineError, match="order"):
        embed_chunks(chunks=(chunk,), provider=StaticProvider(result))


def test_embed_chunks_rejects_vector_count_mismatch() -> None:
    chunks = (_chunk(chunk_index=0), _chunk(chunk_index=1), _chunk(chunk_index=2))
    result = _result_for_ids((chunks[0].chunk_id, chunks[1].chunk_id))

    with pytest.raises(EmbeddingPipelineError, match="number"):
        embed_chunks(chunks=chunks, provider=StaticProvider(result))


def _source() -> DocumentSource:
    return DocumentSource(
        filename="sample.pdf",
        media_type="application/pdf",
        size_bytes=128,
    )


def _chunk(
    *,
    text: str = "Chunk text",
    chunk_index: int = 0,
    chunk_id: UUID | None = None,
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id or uuid4(),
        document_id=uuid4(),
        source=_source(),
        page_number=1,
        chunk_index=chunk_index,
        text=text,
    )


def _result_for_ids(item_ids: tuple[UUID, ...]) -> EmbeddingResult:
    return EmbeddingResult(
        model="static-test-model",
        dimensions=1,
        vectors=tuple(
            EmbeddingVector(item_id=item_id, values=(float(index),))
            for index, item_id in enumerate(item_ids, start=1)
        ),
    )
