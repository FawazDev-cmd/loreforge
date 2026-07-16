from uuid import UUID, uuid4

import pytest

from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.reranking import (
    RerankedSearchResponse,
    RerankingPipelineError,
    RerankingRequest,
    RerankingScore,
    rerank_hybrid_results,
)
from loreforge.retrieval import HybridSearchResult, RetrievalContribution


class DeterministicProvider:
    def __init__(self, scores: tuple[RerankingScore, ...] | None = None) -> None:
        self.scores = scores
        self.calls: list[tuple[RerankingRequest, ...]] = []

    def score(
        self, requests: tuple[RerankingRequest, ...]
    ) -> tuple[RerankingScore, ...]:
        self.calls.append(requests)
        if self.scores is not None:
            return self.scores
        return tuple(
            RerankingScore(item_id=request.item_id, score=float(index))
            for index, request in enumerate(requests, start=1)
        )


class FailingProvider:
    def score(
        self, requests: tuple[RerankingRequest, ...]
    ) -> tuple[RerankingScore, ...]:
        raise RuntimeError("provider failure")


def test_rerank_one_candidate() -> None:
    candidate = _hybrid_result(text="one", rank=1)

    response = rerank_hybrid_results(
        question="question",
        candidates=(candidate,),
        provider=DeterministicProvider(),
        top_k=1,
    )

    assert isinstance(response, RerankedSearchResponse)
    assert response.results[0].hybrid_result == candidate
    assert response.results[0].reranker_score == 1.0
    assert response.results[0].rank == 1


def test_rerank_multiple_candidates_by_score() -> None:
    first = _hybrid_result(text="first", rank=1)
    second = _hybrid_result(text="second", rank=2)
    provider = DeterministicProvider(
        scores=(
            RerankingScore(item_id=first.chunk.chunk_id, score=0.1),
            RerankingScore(item_id=second.chunk.chunk_id, score=2.0),
        )
    )

    response = rerank_hybrid_results(
        question="question",
        candidates=(first, second),
        provider=provider,
        top_k=2,
    )

    assert [result.hybrid_result for result in response.results] == [second, first]


def test_rerank_preserves_original_hybrid_metadata() -> None:
    candidate = _hybrid_result(text="metadata", rank=3)

    response = rerank_hybrid_results(
        question="question",
        candidates=(candidate,),
        provider=DeterministicProvider(),
        top_k=1,
    )

    assert response.results[0].hybrid_result == candidate
    assert response.results[0].hybrid_result.contributions == candidate.contributions


def test_rerank_calls_provider_exactly_once() -> None:
    provider = DeterministicProvider()

    rerank_hybrid_results(
        question="question",
        candidates=(_hybrid_result(), _hybrid_result(text="second", rank=2)),
        provider=provider,
        top_k=2,
    )

    assert len(provider.calls) == 1


def test_rerank_provider_receives_question_and_chunk_text() -> None:
    candidate = _hybrid_result(text="Exact chunk text")
    provider = DeterministicProvider()

    rerank_hybrid_results(
        question="Exact question?",
        candidates=(candidate,),
        provider=provider,
        top_k=1,
    )

    assert provider.calls[0] == (
        RerankingRequest(
            item_id=candidate.chunk.chunk_id,
            query="Exact question?",
            passage="Exact chunk text",
        ),
    )


def test_rerank_top_k_limits_output() -> None:
    response = rerank_hybrid_results(
        question="question",
        candidates=(_hybrid_result(), _hybrid_result(text="second", rank=2)),
        provider=DeterministicProvider(),
        top_k=1,
    )

    assert len(response.results) == 1


def test_rerank_top_k_above_count_returns_all() -> None:
    response = rerank_hybrid_results(
        question="question",
        candidates=(_hybrid_result(),),
        provider=DeterministicProvider(),
        top_k=99,
    )

    assert len(response.results) == 1


def test_rerank_equal_scores_use_original_hybrid_rank() -> None:
    first = _hybrid_result(text="first", rank=1)
    second = _hybrid_result(text="second", rank=2)
    provider = DeterministicProvider(
        scores=(
            RerankingScore(item_id=second.chunk.chunk_id, score=1.0),
            RerankingScore(item_id=first.chunk.chunk_id, score=1.0),
        )
    )

    response = rerank_hybrid_results(
        question="q", candidates=(second, first), provider=provider, top_k=2
    )

    assert [result.hybrid_result for result in response.results] == [first, second]


def test_rerank_remaining_tie_uses_uuid_order() -> None:
    later = _hybrid_result(
        chunk_id=UUID("00000000-0000-0000-0000-000000000002"), text="later", rank=1
    )
    earlier = _hybrid_result(
        chunk_id=UUID("00000000-0000-0000-0000-000000000001"), text="earlier", rank=1
    )
    provider = DeterministicProvider(
        scores=(
            RerankingScore(item_id=later.chunk.chunk_id, score=1.0),
            RerankingScore(item_id=earlier.chunk.chunk_id, score=1.0),
        )
    )

    response = rerank_hybrid_results(
        question="q", candidates=(later, earlier), provider=provider, top_k=2
    )

    assert [result.hybrid_result.chunk.chunk_id for result in response.results] == [
        earlier.chunk.chunk_id,
        later.chunk.chunk_id,
    ]


def test_rerank_final_ranks_are_sequential() -> None:
    response = rerank_hybrid_results(
        question="question",
        candidates=(_hybrid_result(), _hybrid_result(text="second", rank=2)),
        provider=DeterministicProvider(),
        top_k=2,
    )

    assert [result.rank for result in response.results] == [1, 2]


def test_rerank_repeated_calls_are_deterministic() -> None:
    candidates = (_hybrid_result(), _hybrid_result(text="second", rank=2))

    first = rerank_hybrid_results(
        question="q", candidates=candidates, provider=DeterministicProvider(), top_k=2
    )
    second = rerank_hybrid_results(
        question="q", candidates=candidates, provider=DeterministicProvider(), top_k=2
    )

    assert first == second


def test_rerank_does_not_mutate_candidates() -> None:
    candidates = (_hybrid_result(),)
    before = candidates

    rerank_hybrid_results(
        question="q", candidates=candidates, provider=DeterministicProvider(), top_k=1
    )

    assert candidates == before


def test_rerank_empty_candidates_return_empty_response() -> None:
    response = rerank_hybrid_results(
        question="q", candidates=(), provider=DeterministicProvider(), top_k=1
    )

    assert response.results == ()


def test_rerank_does_not_call_provider_for_empty_candidates() -> None:
    provider = DeterministicProvider()

    rerank_hybrid_results(question="q", candidates=(), provider=provider, top_k=1)

    assert provider.calls == []


def test_rerank_rejects_blank_question() -> None:
    with pytest.raises(ValueError, match="question"):
        rerank_hybrid_results(
            question=" ", candidates=(), provider=DeterministicProvider(), top_k=1
        )


def test_rerank_rejects_non_positive_top_k() -> None:
    with pytest.raises(ValueError, match="top_k"):
        rerank_hybrid_results(
            question="q", candidates=(), provider=DeterministicProvider(), top_k=0
        )


def test_rerank_rejects_missing_score() -> None:
    candidate = _hybrid_result()

    with pytest.raises(RerankingPipelineError, match="number"):
        rerank_hybrid_results(
            question="q",
            candidates=(candidate,),
            provider=DeterministicProvider(scores=()),
            top_k=1,
        )


def test_rerank_rejects_extra_score() -> None:
    candidate = _hybrid_result()

    with pytest.raises(RerankingPipelineError, match="number"):
        rerank_hybrid_results(
            question="q",
            candidates=(candidate,),
            provider=DeterministicProvider(
                scores=(
                    RerankingScore(item_id=candidate.chunk.chunk_id, score=1.0),
                    RerankingScore(item_id=uuid4(), score=2.0),
                )
            ),
            top_k=1,
        )


def test_rerank_rejects_reordered_scores() -> None:
    first = _hybrid_result(text="first", rank=1)
    second = _hybrid_result(text="second", rank=2)

    with pytest.raises(RerankingPipelineError, match="order"):
        rerank_hybrid_results(
            question="q",
            candidates=(first, second),
            provider=DeterministicProvider(
                scores=(
                    RerankingScore(item_id=second.chunk.chunk_id, score=2.0),
                    RerankingScore(item_id=first.chunk.chunk_id, score=1.0),
                )
            ),
            top_k=2,
        )


def test_rerank_rejects_mismatched_item_id() -> None:
    candidate = _hybrid_result()

    with pytest.raises(RerankingPipelineError, match="order"):
        rerank_hybrid_results(
            question="q",
            candidates=(candidate,),
            provider=DeterministicProvider(
                scores=(RerankingScore(item_id=uuid4(), score=1.0),)
            ),
            top_k=1,
        )


def test_rerank_provider_errors_propagate_unchanged() -> None:
    with pytest.raises(RuntimeError, match="provider failure"):
        rerank_hybrid_results(
            question="q",
            candidates=(_hybrid_result(),),
            provider=FailingProvider(),
            top_k=1,
        )


def _source() -> DocumentSource:
    return DocumentSource(
        filename="sample.pdf", media_type="application/pdf", size_bytes=128
    )


def _chunk(*, chunk_id: UUID | None = None, text: str = "Chunk text") -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id or uuid4(),
        document_id=uuid4(),
        source=_source(),
        page_number=1,
        chunk_index=0,
        text=text,
    )


def _hybrid_result(
    *,
    chunk_id: UUID | None = None,
    text: str = "Chunk text",
    rank: int = 1,
) -> HybridSearchResult:
    return HybridSearchResult(
        chunk=_chunk(chunk_id=chunk_id, text=text),
        fused_score=1.0,
        rank=rank,
        contributions=(RetrievalContribution(strategy="semantic", rank=1, score=0.5),),
    )
