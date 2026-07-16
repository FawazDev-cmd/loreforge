from dataclasses import FrozenInstanceError
from math import inf, nan
from uuid import uuid4

import pytest

from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.retrieval import (
    LexicalSearchRequest,
    LexicalSearchResponse,
    LexicalSearchResult,
)


def test_lexical_search_request_accepts_valid_values() -> None:
    request = LexicalSearchRequest(query="leave policy", top_k=3)

    assert request.query == "leave policy"
    assert request.top_k == 3


@pytest.mark.parametrize("query", ["", "   "])
def test_lexical_search_request_rejects_blank_query(query: str) -> None:
    with pytest.raises(ValueError, match="query"):
        LexicalSearchRequest(query=query, top_k=1)


@pytest.mark.parametrize("top_k", [0, -1])
def test_lexical_search_request_rejects_non_positive_top_k(top_k: int) -> None:
    with pytest.raises(ValueError, match="top_k"):
        LexicalSearchRequest(query="policy", top_k=top_k)


def test_lexical_search_request_is_immutable() -> None:
    request = LexicalSearchRequest(query="policy", top_k=1)

    with pytest.raises(FrozenInstanceError):
        request.top_k = 2


def test_lexical_search_result_accepts_valid_values() -> None:
    chunk = _chunk()

    result = LexicalSearchResult(chunk=chunk, score=1.0, rank=1)

    assert result.chunk == chunk
    assert result.score == 1.0
    assert result.rank == 1


def test_lexical_search_result_rejects_integer_score() -> None:
    with pytest.raises(ValueError, match="score"):
        LexicalSearchResult(chunk=_chunk(), score=1, rank=1)  # type: ignore[arg-type]


def test_lexical_search_result_rejects_boolean_score() -> None:
    with pytest.raises(ValueError, match="score"):
        LexicalSearchResult(chunk=_chunk(), score=True, rank=1)  # type: ignore[arg-type]


def test_lexical_search_result_rejects_negative_score() -> None:
    with pytest.raises(ValueError, match="score"):
        LexicalSearchResult(chunk=_chunk(), score=-0.1, rank=1)


@pytest.mark.parametrize("score", [nan, inf, -inf])
def test_lexical_search_result_rejects_non_finite_score(score: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        LexicalSearchResult(chunk=_chunk(), score=score, rank=1)


def test_lexical_search_result_rejects_rank_below_one() -> None:
    with pytest.raises(ValueError, match="rank"):
        LexicalSearchResult(chunk=_chunk(), score=1.0, rank=0)


def test_lexical_search_result_is_immutable() -> None:
    result = LexicalSearchResult(chunk=_chunk(), score=1.0, rank=1)

    with pytest.raises(FrozenInstanceError):
        result.rank = 2


def test_lexical_search_response_accepts_non_empty_results() -> None:
    chunk = _chunk()
    result = LexicalSearchResult(chunk=chunk, score=1.0, rank=1)

    response = LexicalSearchResponse(query="policy", results=(result,))

    assert response.query == "policy"
    assert response.results == (result,)


def test_lexical_search_response_accepts_empty_results() -> None:
    response = LexicalSearchResponse(query="missing", results=())

    assert response.results == ()


def test_lexical_search_response_rejects_blank_query() -> None:
    with pytest.raises(ValueError, match="query"):
        LexicalSearchResponse(query=" ", results=())


def test_lexical_search_response_rejects_duplicate_chunk_ids() -> None:
    chunk = _chunk()

    with pytest.raises(ValueError, match="unique"):
        LexicalSearchResponse(
            query="policy",
            results=(
                LexicalSearchResult(chunk=chunk, score=2.0, rank=1),
                LexicalSearchResult(chunk=chunk, score=1.0, rank=2),
            ),
        )


def test_lexical_search_response_rejects_non_sequential_ranks() -> None:
    with pytest.raises(ValueError, match="sequential"):
        LexicalSearchResponse(
            query="policy",
            results=(LexicalSearchResult(chunk=_chunk(), score=1.0, rank=2),),
        )


def test_lexical_search_response_preserves_supplied_order() -> None:
    first = LexicalSearchResult(chunk=_chunk(text="first"), score=1.0, rank=1)
    second = LexicalSearchResult(chunk=_chunk(text="second"), score=0.5, rank=2)

    response = LexicalSearchResponse(query="policy", results=(first, second))

    assert response.results == (first, second)


def test_lexical_search_response_is_immutable() -> None:
    response = LexicalSearchResponse(query="policy", results=())

    with pytest.raises(FrozenInstanceError):
        response.results = ()


def _source() -> DocumentSource:
    return DocumentSource(
        filename="sample.pdf",
        media_type="application/pdf",
        size_bytes=128,
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
