from dataclasses import FrozenInstanceError
from math import inf, nan
from uuid import uuid4

import pytest

from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.reranking import (
    RerankedSearchResponse,
    RerankedSearchResult,
    RerankingRequest,
    RerankingScore,
)
from loreforge.retrieval import HybridSearchResult, RetrievalContribution


def test_reranking_request_accepts_valid_values() -> None:
    item_id = uuid4()

    request = RerankingRequest(item_id=item_id, query="question", passage="passage")

    assert request.item_id == item_id
    assert request.query == "question"
    assert request.passage == "passage"


@pytest.mark.parametrize("query", ["", "   "])
def test_reranking_request_rejects_blank_query(query: str) -> None:
    with pytest.raises(ValueError, match="query"):
        RerankingRequest(item_id=uuid4(), query=query, passage="passage")


@pytest.mark.parametrize("passage", ["", "   "])
def test_reranking_request_rejects_blank_passage(passage: str) -> None:
    with pytest.raises(ValueError, match="passage"):
        RerankingRequest(item_id=uuid4(), query="question", passage=passage)


def test_reranking_request_is_immutable() -> None:
    request = RerankingRequest(item_id=uuid4(), query="question", passage="passage")

    with pytest.raises(FrozenInstanceError):
        request.query = "changed"


def test_reranking_score_accepts_positive_score() -> None:
    score = RerankingScore(item_id=uuid4(), score=1.25)

    assert score.score == 1.25


def test_reranking_score_accepts_negative_score() -> None:
    score = RerankingScore(item_id=uuid4(), score=-1.25)

    assert score.score == -1.25


def test_reranking_score_rejects_integer_score() -> None:
    with pytest.raises(ValueError, match="score"):
        RerankingScore(item_id=uuid4(), score=1)  # type: ignore[arg-type]


def test_reranking_score_rejects_boolean_score() -> None:
    with pytest.raises(ValueError, match="score"):
        RerankingScore(item_id=uuid4(), score=True)  # type: ignore[arg-type]


@pytest.mark.parametrize("score", [nan, inf, -inf])
def test_reranking_score_rejects_non_finite_score(score: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        RerankingScore(item_id=uuid4(), score=score)


def test_reranking_score_is_immutable() -> None:
    score = RerankingScore(item_id=uuid4(), score=1.0)

    with pytest.raises(FrozenInstanceError):
        score.score = 2.0


def test_reranked_search_result_accepts_valid_values() -> None:
    hybrid_result = _hybrid_result(rank=1)

    result = RerankedSearchResult(
        hybrid_result=hybrid_result, reranker_score=2.0, rank=1
    )

    assert result.hybrid_result == hybrid_result
    assert result.reranker_score == 2.0
    assert result.rank == 1


def test_reranked_search_result_accepts_negative_score() -> None:
    result = RerankedSearchResult(
        hybrid_result=_hybrid_result(), reranker_score=-2.0, rank=1
    )

    assert result.reranker_score == -2.0


def test_reranked_search_result_rejects_integer_score() -> None:
    with pytest.raises(ValueError, match="reranker_score"):
        RerankedSearchResult(hybrid_result=_hybrid_result(), reranker_score=1, rank=1)  # type: ignore[arg-type]


def test_reranked_search_result_rejects_boolean_score() -> None:
    with pytest.raises(ValueError, match="reranker_score"):
        RerankedSearchResult(
            hybrid_result=_hybrid_result(), reranker_score=True, rank=1
        )  # type: ignore[arg-type]


@pytest.mark.parametrize("score", [nan, inf, -inf])
def test_reranked_search_result_rejects_non_finite_score(score: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        RerankedSearchResult(
            hybrid_result=_hybrid_result(), reranker_score=score, rank=1
        )


def test_reranked_search_result_rejects_rank_below_one() -> None:
    with pytest.raises(ValueError, match="rank"):
        RerankedSearchResult(hybrid_result=_hybrid_result(), reranker_score=1.0, rank=0)


def test_reranked_search_result_is_immutable() -> None:
    result = RerankedSearchResult(
        hybrid_result=_hybrid_result(), reranker_score=1.0, rank=1
    )

    with pytest.raises(FrozenInstanceError):
        result.rank = 2


def test_reranked_search_response_accepts_populated_response() -> None:
    result = RerankedSearchResult(
        hybrid_result=_hybrid_result(), reranker_score=1.0, rank=1
    )

    response = RerankedSearchResponse(question="question", results=(result,))

    assert response.results == (result,)


def test_reranked_search_response_accepts_empty_response() -> None:
    response = RerankedSearchResponse(question="question", results=())

    assert response.results == ()


def test_reranked_search_response_rejects_blank_question() -> None:
    with pytest.raises(ValueError, match="question"):
        RerankedSearchResponse(question=" ", results=())


def test_reranked_search_response_rejects_duplicate_chunk_ids() -> None:
    hybrid_result = _hybrid_result()

    with pytest.raises(ValueError, match="unique"):
        RerankedSearchResponse(
            question="question",
            results=(
                RerankedSearchResult(
                    hybrid_result=hybrid_result, reranker_score=2.0, rank=1
                ),
                RerankedSearchResult(
                    hybrid_result=hybrid_result, reranker_score=1.0, rank=2
                ),
            ),
        )


def test_reranked_search_response_rejects_non_sequential_ranks() -> None:
    with pytest.raises(ValueError, match="sequential"):
        RerankedSearchResponse(
            question="question",
            results=(
                RerankedSearchResult(
                    hybrid_result=_hybrid_result(), reranker_score=1.0, rank=2
                ),
            ),
        )


def test_reranked_search_response_preserves_supplied_order() -> None:
    first = RerankedSearchResult(
        hybrid_result=_hybrid_result(text="first", rank=1), reranker_score=2.0, rank=1
    )
    second = RerankedSearchResult(
        hybrid_result=_hybrid_result(text="second", rank=2), reranker_score=1.0, rank=2
    )

    response = RerankedSearchResponse(question="question", results=(first, second))

    assert response.results == (first, second)


def test_reranked_search_response_is_immutable() -> None:
    response = RerankedSearchResponse(question="question", results=())

    with pytest.raises(FrozenInstanceError):
        response.results = ()


def _source() -> DocumentSource:
    return DocumentSource(
        filename="sample.pdf", media_type="application/pdf", size_bytes=128
    )


def _chunk(*, text: str = "Chunk text") -> DocumentChunk:
    return DocumentChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        source=_source(),
        page_number=1,
        chunk_index=0,
        text=text,
    )


def _hybrid_result(*, text: str = "Chunk text", rank: int = 1) -> HybridSearchResult:
    return HybridSearchResult(
        chunk=_chunk(text=text),
        fused_score=1.0,
        rank=rank,
        contributions=(RetrievalContribution(strategy="semantic", rank=1, score=0.5),),
    )
