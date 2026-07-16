from uuid import UUID, uuid4

import pytest

from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.embeddings import EmbeddedChunk, EmbeddingVector
from loreforge.retrieval import (
    SemanticSearchRequest,
    SemanticSearchResponse,
    semantic_search,
)
from loreforge.vector_index import InMemoryVectorIndex, VectorIndexError


class FakeQueryEmbeddingProvider:
    def __init__(self, vector: tuple[float, ...]) -> None:
        self.vector = vector
        self.calls: list[str] = []

    def embed_query(self, question: str) -> EmbeddingVector:
        self.calls.append(question)
        return EmbeddingVector(item_id=uuid4(), values=self.vector)


def test_semantic_search_returns_ranked_results() -> None:
    matching = _embedded(values=(1.0, 0.0), text="Matching chunk", chunk_index=0)
    other = _embedded(values=(0.0, 1.0), text="Other chunk", chunk_index=1)
    index = _index_with(matching, other)
    provider = FakeQueryEmbeddingProvider(vector=(1.0, 0.0))
    request = SemanticSearchRequest(question="Which chunk matches?", top_k=2)

    response = semantic_search(request=request, provider=provider, index=index)

    assert isinstance(response, SemanticSearchResponse)
    assert response.question == "Which chunk matches?"
    assert [result.indexed.chunk for result in response.results] == [
        matching.chunk,
        other.chunk,
    ]
    assert [result.rank for result in response.results] == [1, 2]


def test_semantic_search_honors_top_k() -> None:
    index = _index_with(
        _embedded(values=(1.0, 0.0), chunk_index=0),
        _embedded(values=(0.0, 1.0), chunk_index=1),
    )
    provider = FakeQueryEmbeddingProvider(vector=(1.0, 0.0))

    response = semantic_search(
        request=SemanticSearchRequest(question="Find one", top_k=1),
        provider=provider,
        index=index,
    )

    assert len(response.results) == 1


def test_semantic_search_rejects_blank_question() -> None:
    with pytest.raises(ValueError, match="question"):
        SemanticSearchRequest(question=" ", top_k=1)


def test_semantic_search_rejects_invalid_top_k() -> None:
    with pytest.raises(ValueError, match="top_k"):
        SemanticSearchRequest(question="Find", top_k=0)


def test_semantic_search_calls_provider_once() -> None:
    index = _index_with(_embedded(values=(1.0, 0.0)))
    provider = FakeQueryEmbeddingProvider(vector=(1.0, 0.0))

    semantic_search(
        request=SemanticSearchRequest(question="Find", top_k=1),
        provider=provider,
        index=index,
    )

    assert provider.calls == ["Find"]


def test_semantic_search_invokes_query_embedding() -> None:
    index = _index_with(_embedded(values=(1.0, 0.0)))
    provider = FakeQueryEmbeddingProvider(vector=(1.0, 0.0))

    semantic_search(
        request=SemanticSearchRequest(question="Embed this query", top_k=1),
        provider=provider,
        index=index,
    )

    assert provider.calls == ["Embed this query"]


def test_semantic_search_preserves_vector_index_deterministic_ordering() -> None:
    later_id = UUID("00000000-0000-0000-0000-000000000002")
    earlier_id = UUID("00000000-0000-0000-0000-000000000001")
    later = _embedded(values=(1.0, 0.0), chunk_id=later_id, chunk_index=0)
    earlier = _embedded(values=(1.0, 0.0), chunk_id=earlier_id, chunk_index=1)
    index = _index_with(later, earlier)
    provider = FakeQueryEmbeddingProvider(vector=(1.0, 0.0))

    response = semantic_search(
        request=SemanticSearchRequest(question="Tie", top_k=2),
        provider=provider,
        index=index,
    )

    assert [result.indexed.chunk.chunk_id for result in response.results] == [
        earlier_id,
        later_id,
    ]


def test_semantic_search_rejects_empty_index() -> None:
    with pytest.raises(VectorIndexError, match="empty"):
        semantic_search(
            request=SemanticSearchRequest(question="Find", top_k=1),
            provider=FakeQueryEmbeddingProvider(vector=(1.0,)),
            index=InMemoryVectorIndex(),
        )


def test_semantic_search_rejects_invalid_provider_response() -> None:
    index = _index_with(_embedded(values=(1.0, 0.0)))

    with pytest.raises(VectorIndexError, match="dimensions"):
        semantic_search(
            request=SemanticSearchRequest(question="Find", top_k=1),
            provider=FakeQueryEmbeddingProvider(vector=(1.0,)),
            index=index,
        )


def test_semantic_search_returns_immutable_response_results_tuple() -> None:
    index = _index_with(_embedded(values=(1.0, 0.0)))

    response = semantic_search(
        request=SemanticSearchRequest(question="Find", top_k=1),
        provider=FakeQueryEmbeddingProvider(vector=(1.0, 0.0)),
        index=index,
    )

    assert isinstance(response.results, tuple)
    with pytest.raises(AttributeError):
        response.results.append(response.results[0])  # type: ignore[attr-defined]


def test_semantic_search_does_not_mutate_index() -> None:
    item = _embedded(values=(1.0, 0.0))
    index = _index_with(item)

    semantic_search(
        request=SemanticSearchRequest(question="Find", top_k=1),
        provider=FakeQueryEmbeddingProvider(vector=(1.0, 0.0)),
        index=index,
    )

    assert index.size == 1
    assert index.get(item.chunk.chunk_id) is not None


def _index_with(*items: EmbeddedChunk) -> InMemoryVectorIndex:
    index = InMemoryVectorIndex()
    index.add(tuple(items))
    return index


def _source() -> DocumentSource:
    return DocumentSource(
        filename="sample.pdf",
        media_type="application/pdf",
        size_bytes=128,
    )


def _chunk(
    *,
    chunk_id: UUID | None = None,
    chunk_index: int = 0,
    text: str = "Chunk text",
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id or uuid4(),
        document_id=uuid4(),
        source=_source(),
        page_number=1,
        chunk_index=chunk_index,
        text=text,
    )


def _embedded(
    *,
    values: tuple[float, ...],
    chunk_id: UUID | None = None,
    chunk_index: int = 0,
    text: str = "Chunk text",
) -> EmbeddedChunk:
    chunk = _chunk(chunk_id=chunk_id, chunk_index=chunk_index, text=text)
    return EmbeddedChunk(
        chunk=chunk,
        vector=EmbeddingVector(item_id=chunk.chunk_id, values=values),
    )
