from dataclasses import FrozenInstanceError
from math import inf, nan
from uuid import uuid4

import pytest

from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.retrieval import (
    HybridSearchRequest,
    HybridSearchResponse,
    HybridSearchResult,
    RetrievalContribution,
)


def test_retrieval_contribution_accepts_semantic() -> None:
    contribution = RetrievalContribution(strategy="semantic", rank=1, score=-0.5)

    assert contribution.strategy == "semantic"
    assert contribution.rank == 1
    assert contribution.score == -0.5


def test_retrieval_contribution_accepts_lexical() -> None:
    contribution = RetrievalContribution(strategy="lexical", rank=2, score=1.5)

    assert contribution.strategy == "lexical"
    assert contribution.rank == 2
    assert contribution.score == 1.5


def test_retrieval_contribution_rejects_blank_strategy() -> None:
    with pytest.raises(ValueError, match="strategy"):
        RetrievalContribution(strategy=" ", rank=1, score=1.0)


def test_retrieval_contribution_rejects_integer_score() -> None:
    with pytest.raises(ValueError, match="score"):
        RetrievalContribution(strategy="semantic", rank=1, score=1)  # type: ignore[arg-type]


def test_retrieval_contribution_rejects_boolean_score() -> None:
    with pytest.raises(ValueError, match="score"):
        RetrievalContribution(strategy="semantic", rank=1, score=True)  # type: ignore[arg-type]


@pytest.mark.parametrize("score", [nan, inf, -inf])
def test_retrieval_contribution_rejects_non_finite_scores(score: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        RetrievalContribution(strategy="semantic", rank=1, score=score)


def test_retrieval_contribution_rejects_rank_below_one() -> None:
    with pytest.raises(ValueError, match="rank"):
        RetrievalContribution(strategy="semantic", rank=0, score=1.0)


def test_retrieval_contribution_is_immutable() -> None:
    contribution = RetrievalContribution(strategy="semantic", rank=1, score=1.0)

    with pytest.raises(FrozenInstanceError):
        contribution.rank = 2


def test_hybrid_search_request_accepts_defaults() -> None:
    request = HybridSearchRequest(question="What is leave policy?")

    assert request.question == "What is leave policy?"
    assert request.top_k == 5
    assert request.semantic_top_k == 10
    assert request.lexical_top_k == 10


def test_hybrid_search_request_rejects_blank_question() -> None:
    with pytest.raises(ValueError, match="question"):
        HybridSearchRequest(question=" ")


@pytest.mark.parametrize("field", ["top_k", "semantic_top_k", "lexical_top_k"])
def test_hybrid_search_request_rejects_non_positive_top_k_values(field: str) -> None:
    kwargs = {field: 0}

    with pytest.raises(ValueError, match=field):
        HybridSearchRequest(question="Find policy", **kwargs)  # type: ignore[arg-type]


def test_hybrid_search_request_is_immutable() -> None:
    request = HybridSearchRequest(question="Find policy")

    with pytest.raises(FrozenInstanceError):
        request.top_k = 2


def test_hybrid_search_result_accepts_semantic_only() -> None:
    result = HybridSearchResult(
        chunk=_chunk(),
        fused_score=0.1,
        rank=1,
        contributions=(_semantic_contribution(),),
    )

    assert result.contributions[0].strategy == "semantic"


def test_hybrid_search_result_accepts_lexical_only() -> None:
    result = HybridSearchResult(
        chunk=_chunk(),
        fused_score=0.1,
        rank=1,
        contributions=(_lexical_contribution(),),
    )

    assert result.contributions[0].strategy == "lexical"


def test_hybrid_search_result_accepts_two_strategy_result() -> None:
    result = HybridSearchResult(
        chunk=_chunk(),
        fused_score=0.2,
        rank=1,
        contributions=(_semantic_contribution(), _lexical_contribution()),
    )

    assert [contribution.strategy for contribution in result.contributions] == [
        "semantic",
        "lexical",
    ]


def test_hybrid_search_result_rejects_non_positive_fused_score() -> None:
    with pytest.raises(ValueError, match="fused_score"):
        HybridSearchResult(
            chunk=_chunk(),
            fused_score=0.0,
            rank=1,
            contributions=(_semantic_contribution(),),
        )


def test_hybrid_search_result_rejects_non_float_fused_score() -> None:
    with pytest.raises(ValueError, match="fused_score"):
        HybridSearchResult(
            chunk=_chunk(),
            fused_score=1,
            rank=1,
            contributions=(_semantic_contribution(),),
        )  # type: ignore[arg-type]


def test_hybrid_search_result_rejects_duplicate_contribution_strategy() -> None:
    with pytest.raises(ValueError, match="unique"):
        HybridSearchResult(
            chunk=_chunk(),
            fused_score=0.2,
            rank=1,
            contributions=(_semantic_contribution(), _semantic_contribution(rank=2)),
        )


def test_hybrid_search_result_rejects_no_contributions() -> None:
    with pytest.raises(ValueError, match="contributions"):
        HybridSearchResult(chunk=_chunk(), fused_score=0.1, rank=1, contributions=())


def test_hybrid_search_result_rejects_wrong_contribution_ordering() -> None:
    with pytest.raises(ValueError, match="ordered"):
        HybridSearchResult(
            chunk=_chunk(),
            fused_score=0.2,
            rank=1,
            contributions=(_lexical_contribution(), _semantic_contribution()),
        )


def test_hybrid_search_result_rejects_invalid_rank() -> None:
    with pytest.raises(ValueError, match="rank"):
        HybridSearchResult(
            chunk=_chunk(),
            fused_score=0.1,
            rank=0,
            contributions=(_semantic_contribution(),),
        )


def test_hybrid_search_result_is_immutable() -> None:
    result = HybridSearchResult(
        chunk=_chunk(),
        fused_score=0.1,
        rank=1,
        contributions=(_semantic_contribution(),),
    )

    with pytest.raises(FrozenInstanceError):
        result.rank = 2


def test_hybrid_search_response_accepts_populated_response() -> None:
    result = HybridSearchResult(
        chunk=_chunk(),
        fused_score=0.1,
        rank=1,
        contributions=(_semantic_contribution(),),
    )

    response = HybridSearchResponse(question="Find", results=(result,))

    assert response.results == (result,)


def test_hybrid_search_response_accepts_empty_response() -> None:
    response = HybridSearchResponse(question="Find", results=())

    assert response.results == ()


def test_hybrid_search_response_rejects_blank_question() -> None:
    with pytest.raises(ValueError, match="question"):
        HybridSearchResponse(question=" ", results=())


def test_hybrid_search_response_rejects_duplicate_chunk_ids() -> None:
    chunk = _chunk()

    with pytest.raises(ValueError, match="unique"):
        HybridSearchResponse(
            question="Find",
            results=(
                HybridSearchResult(
                    chunk=chunk,
                    fused_score=0.2,
                    rank=1,
                    contributions=(_semantic_contribution(),),
                ),
                HybridSearchResult(
                    chunk=chunk,
                    fused_score=0.1,
                    rank=2,
                    contributions=(_lexical_contribution(),),
                ),
            ),
        )


def test_hybrid_search_response_rejects_non_sequential_ranks() -> None:
    with pytest.raises(ValueError, match="sequential"):
        HybridSearchResponse(
            question="Find",
            results=(
                HybridSearchResult(
                    chunk=_chunk(),
                    fused_score=0.1,
                    rank=2,
                    contributions=(_semantic_contribution(),),
                ),
            ),
        )


def test_hybrid_search_response_preserves_supplied_order() -> None:
    first = HybridSearchResult(
        chunk=_chunk(text="first"),
        fused_score=0.2,
        rank=1,
        contributions=(_semantic_contribution(),),
    )
    second = HybridSearchResult(
        chunk=_chunk(text="second"),
        fused_score=0.1,
        rank=2,
        contributions=(_lexical_contribution(),),
    )

    response = HybridSearchResponse(question="Find", results=(first, second))

    assert response.results == (first, second)


def test_hybrid_search_response_is_immutable() -> None:
    response = HybridSearchResponse(question="Find", results=())

    with pytest.raises(FrozenInstanceError):
        response.results = ()


def _semantic_contribution(
    *, rank: int = 1, score: float = 0.5
) -> RetrievalContribution:
    return RetrievalContribution(strategy="semantic", rank=rank, score=score)


def _lexical_contribution(
    *, rank: int = 1, score: float = 1.0
) -> RetrievalContribution:
    return RetrievalContribution(strategy="lexical", rank=rank, score=score)


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
