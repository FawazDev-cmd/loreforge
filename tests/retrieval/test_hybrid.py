from uuid import UUID, uuid4

import pytest

from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.embeddings import EmbeddedChunk, EmbeddingVector
from loreforge.retrieval import (
    BM25IndexError,
    HybridRetrievalError,
    HybridSearchRequest,
    InMemoryBM25Index,
    LexicalSearchRequest,
    LexicalSearchResult,
    hybrid_search,
    reciprocal_rank_fusion,
)
from loreforge.vector_index import (
    IndexedVector,
    InMemoryVectorIndex,
    VectorIndexError,
    VectorSearchResult,
)


class FakeQueryEmbeddingProvider:
    def __init__(self, vector: tuple[float, ...]) -> None:
        self.vector = vector
        self.calls: list[str] = []

    def embed_query(self, question: str) -> EmbeddingVector:
        self.calls.append(question)
        return EmbeddingVector(item_id=uuid4(), values=self.vector)


class SpyVectorIndex(InMemoryVectorIndex):
    def __init__(self) -> None:
        super().__init__()
        self.search_top_k_values: list[int] = []

    def search(
        self, *, query_vector: tuple[float, ...], top_k: int
    ) -> tuple[VectorSearchResult, ...]:
        self.search_top_k_values.append(top_k)
        return super().search(query_vector=query_vector, top_k=top_k)


class SpyBM25Index(InMemoryBM25Index):
    def __init__(self) -> None:
        super().__init__()
        self.search_top_k_values: list[int] = []
        self.queries: list[str] = []

    def search(self, request: LexicalSearchRequest):  # type: ignore[no-untyped-def]
        self.search_top_k_values.append(request.top_k)
        self.queries.append(request.query)
        return super().search(request)


class EmptyVectorIndex:
    def __init__(self) -> None:
        self.search_top_k_values: list[int] = []

    def search(
        self, *, query_vector: tuple[float, ...], top_k: int
    ) -> tuple[VectorSearchResult, ...]:
        self.search_top_k_values.append(top_k)
        return ()


def test_rrf_includes_semantic_only_chunk() -> None:
    chunk = _chunk(text="semantic")

    results = reciprocal_rank_fusion(
        semantic_results=(_semantic_result(chunk=chunk, score=0.9, rank=1),),
        lexical_results=(),
        top_k=5,
    )

    assert [result.chunk for result in results] == [chunk]
    assert results[0].contributions[0].strategy == "semantic"


def test_rrf_includes_lexical_only_chunk() -> None:
    chunk = _chunk(text="lexical")

    results = reciprocal_rank_fusion(
        semantic_results=(),
        lexical_results=(_lexical_result(chunk=chunk, score=2.0, rank=1),),
        top_k=5,
    )

    assert [result.chunk for result in results] == [chunk]
    assert results[0].contributions[0].strategy == "lexical"


def test_rrf_deduplicates_overlapping_chunk() -> None:
    chunk = _chunk(text="overlap")

    results = reciprocal_rank_fusion(
        semantic_results=(_semantic_result(chunk=chunk, score=0.7, rank=2),),
        lexical_results=(_lexical_result(chunk=chunk, score=1.3, rank=1),),
        top_k=5,
    )

    assert len(results) == 1
    assert results[0].chunk == chunk


def test_rrf_overlapping_chunk_has_both_contributions() -> None:
    chunk = _chunk(text="overlap")

    results = reciprocal_rank_fusion(
        semantic_results=(_semantic_result(chunk=chunk, score=0.7, rank=2),),
        lexical_results=(_lexical_result(chunk=chunk, score=1.3, rank=1),),
        top_k=5,
    )

    assert [contribution.strategy for contribution in results[0].contributions] == [
        "semantic",
        "lexical",
    ]


def test_rrf_fused_score_matches_expected_sum() -> None:
    chunk = _chunk(text="overlap")

    results = reciprocal_rank_fusion(
        semantic_results=(_semantic_result(chunk=chunk, score=0.7, rank=2),),
        lexical_results=(_lexical_result(chunk=chunk, score=1.3, rank=1),),
        top_k=5,
        rrf_k=60,
    )

    assert results[0].fused_score == pytest.approx((1.0 / 62.0) + (1.0 / 61.0))


def test_rrf_preserves_original_strategy_rank_and_score() -> None:
    chunk = _chunk(text="overlap")

    results = reciprocal_rank_fusion(
        semantic_results=(_semantic_result(chunk=chunk, score=-0.25, rank=3),),
        lexical_results=(_lexical_result(chunk=chunk, score=2.5, rank=4),),
        top_k=5,
    )

    assert [(c.strategy, c.rank, c.score) for c in results[0].contributions] == [
        ("semantic", 3, -0.25),
        ("lexical", 4, 2.5),
    ]


def test_rrf_semantic_contribution_precedes_lexical() -> None:
    chunk = _chunk(text="overlap")

    results = reciprocal_rank_fusion(
        semantic_results=(_semantic_result(chunk=chunk, score=0.1, rank=1),),
        lexical_results=(_lexical_result(chunk=chunk, score=0.2, rank=1),),
        top_k=1,
    )

    assert [contribution.strategy for contribution in results[0].contributions] == [
        "semantic",
        "lexical",
    ]


def test_rrf_orders_by_descending_fused_score() -> None:
    first = _chunk(text="first")
    second = _chunk(text="second")

    results = reciprocal_rank_fusion(
        semantic_results=(
            _semantic_result(chunk=second, score=0.2, rank=2),
            _semantic_result(chunk=first, score=0.1, rank=1),
        ),
        lexical_results=(),
        top_k=2,
    )

    assert [result.chunk for result in results] == [first, second]


def test_rrf_applies_deterministic_uuid_tie_break() -> None:
    later = _chunk(chunk_id=UUID("00000000-0000-0000-0000-000000000002"), text="later")
    earlier = _chunk(
        chunk_id=UUID("00000000-0000-0000-0000-000000000001"), text="earlier"
    )

    results = reciprocal_rank_fusion(
        semantic_results=(
            _semantic_result(chunk=later, score=0.2, rank=1),
            _semantic_result(chunk=earlier, score=0.1, rank=1),
        ),
        lexical_results=(),
        top_k=2,
    )

    assert [result.chunk.chunk_id for result in results] == [
        earlier.chunk_id,
        later.chunk_id,
    ]


def test_rrf_final_ranks_are_sequential() -> None:
    results = reciprocal_rank_fusion(
        semantic_results=(
            _semantic_result(chunk=_chunk(text="a"), score=0.2, rank=1),
            _semantic_result(chunk=_chunk(text="b"), score=0.1, rank=2),
        ),
        lexical_results=(),
        top_k=2,
    )

    assert [result.rank for result in results] == [1, 2]


def test_rrf_top_k_limits_output() -> None:
    results = reciprocal_rank_fusion(
        semantic_results=(
            _semantic_result(chunk=_chunk(text="a"), score=0.2, rank=1),
            _semantic_result(chunk=_chunk(text="b"), score=0.1, rank=2),
        ),
        lexical_results=(),
        top_k=1,
    )

    assert len(results) == 1


def test_rrf_top_k_above_unique_count_returns_all() -> None:
    results = reciprocal_rank_fusion(
        semantic_results=(_semantic_result(chunk=_chunk(text="a"), score=0.2, rank=1),),
        lexical_results=(),
        top_k=99,
    )

    assert len(results) == 1


def test_rrf_empty_inputs_return_empty_tuple() -> None:
    assert (
        reciprocal_rank_fusion(semantic_results=(), lexical_results=(), top_k=5) == ()
    )


def test_rrf_one_empty_input_fuses_the_other() -> None:
    chunk = _chunk(text="lexical")

    results = reciprocal_rank_fusion(
        semantic_results=(),
        lexical_results=(_lexical_result(chunk=chunk, score=1.0, rank=1),),
        top_k=5,
    )

    assert [result.chunk for result in results] == [chunk]


def test_rrf_repeated_fusion_is_deterministic() -> None:
    semantic = (_semantic_result(chunk=_chunk(text="a"), score=0.2, rank=1),)
    lexical = (_lexical_result(chunk=_chunk(text="b"), score=1.0, rank=1),)

    first = reciprocal_rank_fusion(
        semantic_results=semantic, lexical_results=lexical, top_k=5
    )
    second = reciprocal_rank_fusion(
        semantic_results=semantic, lexical_results=lexical, top_k=5
    )

    assert first == second


def test_rrf_inputs_remain_unchanged() -> None:
    semantic = (_semantic_result(chunk=_chunk(text="a"), score=0.2, rank=1),)
    lexical = (_lexical_result(chunk=_chunk(text="b"), score=1.0, rank=1),)

    reciprocal_rank_fusion(semantic_results=semantic, lexical_results=lexical, top_k=5)

    assert semantic == semantic
    assert lexical == lexical


def test_rrf_conflicting_chunk_values_raise_error() -> None:
    chunk_id = uuid4()
    semantic_chunk = _chunk(chunk_id=chunk_id, text="semantic text")
    lexical_chunk = _chunk(chunk_id=chunk_id, text="lexical text")

    with pytest.raises(HybridRetrievalError, match="conflicting"):
        reciprocal_rank_fusion(
            semantic_results=(
                _semantic_result(chunk=semantic_chunk, score=0.2, rank=1),
            ),
            lexical_results=(_lexical_result(chunk=lexical_chunk, score=1.0, rank=1),),
            top_k=5,
        )


def test_rrf_rejects_non_positive_top_k() -> None:
    with pytest.raises(ValueError, match="top_k"):
        reciprocal_rank_fusion(semantic_results=(), lexical_results=(), top_k=0)


def test_rrf_rejects_non_positive_rrf_k() -> None:
    with pytest.raises(ValueError, match="rrf_k"):
        reciprocal_rank_fusion(
            semantic_results=(), lexical_results=(), top_k=1, rrf_k=0
        )


def test_hybrid_search_invokes_semantic_and_lexical_paths() -> None:
    chunk = _chunk(text="policy")
    vector_index = _spy_vector_index_with(_embedded(chunk=chunk, values=(1.0, 0.0)))
    lexical_index = _spy_bm25_index_with(chunk)
    provider = FakeQueryEmbeddingProvider(vector=(1.0, 0.0))

    hybrid_search(
        request=HybridSearchRequest(
            question="policy", top_k=5, semantic_top_k=3, lexical_top_k=4
        ),
        semantic_provider=provider,
        vector_index=vector_index,
        lexical_index=lexical_index,
    )

    assert provider.calls == ["policy"]
    assert vector_index.search_top_k_values == [3]
    assert lexical_index.search_top_k_values == [4]
    assert lexical_index.queries == ["policy"]


def test_hybrid_search_final_count_uses_top_k() -> None:
    first = _chunk(text="policy alpha", chunk_index=0)
    second = _chunk(text="policy beta", chunk_index=1)
    vector_index = _spy_vector_index_with(
        _embedded(chunk=first, values=(1.0, 0.0)),
        _embedded(chunk=second, values=(0.0, 1.0)),
    )
    lexical_index = _spy_bm25_index_with(first, second)

    response = hybrid_search(
        request=HybridSearchRequest(
            question="policy", top_k=1, semantic_top_k=2, lexical_top_k=2
        ),
        semantic_provider=FakeQueryEmbeddingProvider(vector=(1.0, 0.0)),
        vector_index=vector_index,
        lexical_index=lexical_index,
    )

    assert len(response.results) == 1


def test_hybrid_search_preserves_original_question() -> None:
    chunk = _chunk(text="policy")
    response = hybrid_search(
        request=HybridSearchRequest(question="What is policy?", top_k=1),
        semantic_provider=FakeQueryEmbeddingProvider(vector=(1.0,)),
        vector_index=_spy_vector_index_with(_embedded(chunk=chunk, values=(1.0,))),
        lexical_index=_spy_bm25_index_with(chunk),
    )

    assert response.question == "What is policy?"


def test_hybrid_search_fuses_overlapping_evidence() -> None:
    chunk = _chunk(text="policy")

    response = hybrid_search(
        request=HybridSearchRequest(question="policy", top_k=5),
        semantic_provider=FakeQueryEmbeddingProvider(vector=(1.0,)),
        vector_index=_spy_vector_index_with(_embedded(chunk=chunk, values=(1.0,))),
        lexical_index=_spy_bm25_index_with(chunk),
    )

    assert len(response.results) == 1
    assert [
        contribution.strategy for contribution in response.results[0].contributions
    ] == [
        "semantic",
        "lexical",
    ]


def test_hybrid_search_lexical_no_match_still_returns_semantic_evidence() -> None:
    chunk = _chunk(text="policy")

    response = hybrid_search(
        request=HybridSearchRequest(question="missing", top_k=5),
        semantic_provider=FakeQueryEmbeddingProvider(vector=(1.0,)),
        vector_index=_spy_vector_index_with(_embedded(chunk=chunk, values=(1.0,))),
        lexical_index=_spy_bm25_index_with(chunk),
    )

    assert [result.chunk for result in response.results] == [chunk]
    assert [
        contribution.strategy for contribution in response.results[0].contributions
    ] == ["semantic"]


def test_hybrid_search_is_deterministic() -> None:
    chunk = _chunk(text="policy")
    request = HybridSearchRequest(question="policy", top_k=5)
    provider = FakeQueryEmbeddingProvider(vector=(1.0,))
    vector_index = _spy_vector_index_with(_embedded(chunk=chunk, values=(1.0,)))
    lexical_index = _spy_bm25_index_with(chunk)

    first = hybrid_search(
        request=request,
        semantic_provider=provider,
        vector_index=vector_index,
        lexical_index=lexical_index,
    )
    second = hybrid_search(
        request=request,
        semantic_provider=provider,
        vector_index=vector_index,
        lexical_index=lexical_index,
    )

    assert first == second


def test_hybrid_search_empty_final_evidence_is_valid_when_both_paths_empty() -> None:
    lexical_index = _spy_bm25_index_with(_chunk(text="policy"))

    response = hybrid_search(
        request=HybridSearchRequest(question="missing", top_k=5),
        semantic_provider=FakeQueryEmbeddingProvider(vector=(1.0,)),
        vector_index=EmptyVectorIndex(),  # type: ignore[arg-type]
        lexical_index=lexical_index,
    )

    assert response.results == ()


def test_hybrid_search_upstream_semantic_errors_propagate() -> None:
    with pytest.raises(VectorIndexError):
        hybrid_search(
            request=HybridSearchRequest(question="policy", top_k=5),
            semantic_provider=FakeQueryEmbeddingProvider(vector=(1.0,)),
            vector_index=InMemoryVectorIndex(),
            lexical_index=_spy_bm25_index_with(_chunk(text="policy")),
        )


def test_hybrid_search_upstream_bm25_errors_propagate() -> None:
    chunk = _chunk(text="policy")

    with pytest.raises(BM25IndexError):
        hybrid_search(
            request=HybridSearchRequest(question="policy", top_k=5),
            semantic_provider=FakeQueryEmbeddingProvider(vector=(1.0,)),
            vector_index=_spy_vector_index_with(_embedded(chunk=chunk, values=(1.0,))),
            lexical_index=InMemoryBM25Index(),
        )


def test_hybrid_search_does_not_mutate_indexes() -> None:
    chunk = _chunk(text="policy")
    vector_index = _spy_vector_index_with(_embedded(chunk=chunk, values=(1.0,)))
    lexical_index = _spy_bm25_index_with(chunk)

    hybrid_search(
        request=HybridSearchRequest(question="policy", top_k=5),
        semantic_provider=FakeQueryEmbeddingProvider(vector=(1.0,)),
        vector_index=vector_index,
        lexical_index=lexical_index,
    )

    assert vector_index.size == 1
    assert lexical_index.size == 1
    assert lexical_index.get(chunk.chunk_id) == chunk


def _source() -> DocumentSource:
    return DocumentSource(
        filename="sample.pdf", media_type="application/pdf", size_bytes=128
    )


def _chunk(
    *,
    text: str,
    chunk_id: UUID | None = None,
    chunk_index: int = 0,
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id or uuid4(),
        document_id=uuid4(),
        source=_source(),
        page_number=1,
        chunk_index=chunk_index,
        text=text,
    )


def _embedded(*, chunk: DocumentChunk, values: tuple[float, ...]) -> EmbeddedChunk:
    return EmbeddedChunk(
        chunk=chunk,
        vector=EmbeddingVector(item_id=chunk.chunk_id, values=values),
    )


def _semantic_result(
    *, chunk: DocumentChunk, score: float, rank: int
) -> VectorSearchResult:
    return VectorSearchResult(
        indexed=IndexedVector(
            chunk=chunk,
            vector=EmbeddingVector(item_id=chunk.chunk_id, values=(1.0,)),
        ),
        score=score,
        rank=rank,
    )


def _lexical_result(
    *, chunk: DocumentChunk, score: float, rank: int
) -> LexicalSearchResult:
    return LexicalSearchResult(chunk=chunk, score=score, rank=rank)


def _spy_vector_index_with(*items: EmbeddedChunk) -> SpyVectorIndex:
    index = SpyVectorIndex()
    index.add(tuple(items))
    return index


def _spy_bm25_index_with(*chunks: DocumentChunk) -> SpyBM25Index:
    index = SpyBM25Index()
    index.add(tuple(chunks))
    return index
