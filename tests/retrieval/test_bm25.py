from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

import pytest

from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.retrieval import (
    BM25Config,
    BM25IndexError,
    InMemoryBM25Index,
    LexicalSearchRequest,
)


def test_bm25_config_accepts_defaults() -> None:
    config = BM25Config()

    assert config.k1 == 1.5
    assert config.b == 0.75


@pytest.mark.parametrize("kwargs", [{"k1": 1}, {"b": 1}, {"k1": True}, {"b": False}])
def test_bm25_config_rejects_non_float_parameters(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        BM25Config(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("k1", [0.0, -1.0])
def test_bm25_config_rejects_invalid_k1(k1: float) -> None:
    with pytest.raises(ValueError, match="k1"):
        BM25Config(k1=k1)


@pytest.mark.parametrize("b", [-0.1, 1.1])
def test_bm25_config_rejects_invalid_b(b: float) -> None:
    with pytest.raises(ValueError, match="b"):
        BM25Config(b=b)


def test_bm25_config_is_immutable() -> None:
    config = BM25Config()

    with pytest.raises(FrozenInstanceError):
        config.k1 = 2.0


def test_index_initial_state() -> None:
    index = InMemoryBM25Index()

    assert index.size == 0
    assert index.average_document_length == 0.0
    assert index.get(uuid4()) is None


def test_add_one_chunk() -> None:
    chunk = _chunk(text="leave policy")
    index = InMemoryBM25Index()

    index.add((chunk,))

    assert index.size == 1
    assert index.get(chunk.chunk_id) == chunk
    assert index.average_document_length == pytest.approx(2.0)


def test_add_multiple_chunks() -> None:
    first = _chunk(text="leave policy", chunk_index=0)
    second = _chunk(text="expense policy guide", chunk_index=1)
    index = InMemoryBM25Index()

    index.add((first, second))

    assert index.size == 2
    assert index.average_document_length == pytest.approx(2.5)


def test_add_preserves_complete_provenance() -> None:
    source = DocumentSource(
        filename="handbook.pdf",
        media_type="application/pdf",
        size_bytes=256,
    )
    chunk = _chunk(
        source=source,
        page_number=4,
        chunk_index=2,
        text="leave policy",
    )
    index = InMemoryBM25Index()

    index.add((chunk,))

    stored = index.get(chunk.chunk_id)
    assert stored is not None
    assert stored.document_id == chunk.document_id
    assert stored.source == source
    assert stored.page_number == 4
    assert stored.chunk_index == 2
    assert stored.text == "leave policy"


def test_add_rejects_duplicate_existing_id() -> None:
    chunk = _chunk(text="leave policy")
    index = InMemoryBM25Index()
    index.add((chunk,))

    with pytest.raises(BM25IndexError, match="already exists"):
        index.add((chunk,))


def test_add_rejects_duplicate_batch_id() -> None:
    chunk_id = uuid4()
    first = _chunk(chunk_id=chunk_id, text="leave policy", chunk_index=0)
    second = _chunk(chunk_id=chunk_id, text="expense policy", chunk_index=1)
    index = InMemoryBM25Index()

    with pytest.raises(BM25IndexError, match="duplicate"):
        index.add((first, second))

    assert index.size == 0
    assert index.average_document_length == 0.0


def test_add_rejects_empty_batch() -> None:
    with pytest.raises(BM25IndexError, match="chunks"):
        InMemoryBM25Index().add(())


def test_failed_batch_leaves_state_unchanged() -> None:
    existing = _chunk(text="leave policy", chunk_index=0)
    duplicate = _chunk(
        chunk_id=existing.chunk_id,
        text="expense policy",
        chunk_index=1,
    )
    new_chunk = _chunk(text="payroll guide", chunk_index=2)
    index = InMemoryBM25Index()
    index.add((existing,))

    with pytest.raises(BM25IndexError):
        index.add((duplicate, new_chunk))

    assert index.size == 1
    assert index.get(existing.chunk_id) == existing
    assert index.get(new_chunk.chunk_id) is None
    assert index.average_document_length == pytest.approx(2.0)


def test_search_rare_exact_term_ranks_matching_chunk_first() -> None:
    rare = _chunk(text="zanzibar leave policy", chunk_index=0)
    common = _chunk(text="leave policy handbook", chunk_index=1)
    index = _index_with(rare, common)

    response = index.search(LexicalSearchRequest(query="zanzibar", top_k=2))

    assert [result.chunk for result in response.results] == [rare]


def test_search_term_frequency_affects_score() -> None:
    repeated = _chunk(text="policy policy policy alpha", chunk_index=0)
    once = _chunk(text="policy beta gamma alpha", chunk_index=1)
    index = _index_with(once, repeated)

    response = index.search(LexicalSearchRequest(query="policy", top_k=2))

    assert response.results[0].chunk == repeated
    assert response.results[0].score > response.results[1].score


def test_search_document_length_normalization_affects_score() -> None:
    short = _chunk(text="policy", chunk_index=0)
    long = _chunk(text="policy alpha beta gamma delta epsilon", chunk_index=1)
    index = _index_with(long, short)

    response = index.search(LexicalSearchRequest(query="policy", top_k=2))

    assert response.results[0].chunk == short


def test_search_multiple_matching_query_terms_affect_ranking() -> None:
    two_terms = _chunk(text="leave policy alpha", chunk_index=0)
    one_term = _chunk(text="leave beta gamma", chunk_index=1)
    index = _index_with(one_term, two_terms)

    response = index.search(LexicalSearchRequest(query="leave policy", top_k=2))

    assert response.results[0].chunk == two_terms


def test_search_unmatched_query_returns_empty_results() -> None:
    index = _index_with(_chunk(text="leave policy"))

    response = index.search(LexicalSearchRequest(query="payroll", top_k=5))

    assert response.results == ()


def test_search_omits_zero_score_chunks() -> None:
    matching = _chunk(text="leave policy", chunk_index=0)
    unrelated = _chunk(text="expense report", chunk_index=1)
    index = _index_with(matching, unrelated)

    response = index.search(LexicalSearchRequest(query="leave", top_k=5))

    assert [result.chunk for result in response.results] == [matching]


def test_search_top_k_limits_results() -> None:
    index = _index_with(
        _chunk(text="policy alpha", chunk_index=0),
        _chunk(text="policy beta", chunk_index=1),
    )

    response = index.search(LexicalSearchRequest(query="policy", top_k=1))

    assert len(response.results) == 1


def test_search_top_k_greater_than_matches_returns_all_matches() -> None:
    index = _index_with(
        _chunk(text="policy alpha", chunk_index=0),
        _chunk(text="policy beta", chunk_index=1),
    )

    response = index.search(LexicalSearchRequest(query="policy", top_k=99))

    assert len(response.results) == 2


def test_search_applies_deterministic_uuid_tie_break() -> None:
    later_id = UUID("00000000-0000-0000-0000-000000000002")
    earlier_id = UUID("00000000-0000-0000-0000-000000000001")
    later = _chunk(chunk_id=later_id, text="policy", chunk_index=0)
    earlier = _chunk(chunk_id=earlier_id, text="policy", chunk_index=1)
    index = _index_with(later, earlier)

    response = index.search(LexicalSearchRequest(query="policy", top_k=2))

    assert [result.chunk.chunk_id for result in response.results] == [
        earlier_id,
        later_id,
    ]


def test_search_ranks_are_sequential() -> None:
    index = _index_with(
        _chunk(text="policy alpha", chunk_index=0),
        _chunk(text="policy beta", chunk_index=1),
    )

    response = index.search(LexicalSearchRequest(query="policy", top_k=2))

    assert [result.rank for result in response.results] == [1, 2]


def test_search_result_is_immutable() -> None:
    index = _index_with(_chunk(text="policy"))

    response = index.search(LexicalSearchRequest(query="policy", top_k=1))

    assert isinstance(response.results, tuple)
    with pytest.raises(AttributeError):
        response.results.append(response.results[0])  # type: ignore[attr-defined]


def test_repeated_searches_are_deterministic() -> None:
    index = _index_with(
        _chunk(text="policy alpha", chunk_index=0),
        _chunk(text="policy beta", chunk_index=1),
    )
    request = LexicalSearchRequest(query="policy", top_k=2)

    assert index.search(request) == index.search(request)


def test_search_does_not_mutate_index_state() -> None:
    chunk = _chunk(text="policy")
    index = _index_with(chunk)

    index.search(LexicalSearchRequest(query="policy", top_k=1))

    assert index.size == 1
    assert index.get(chunk.chunk_id) == chunk
    assert index.average_document_length == pytest.approx(1.0)


def test_search_rejects_empty_index() -> None:
    with pytest.raises(BM25IndexError, match="empty"):
        InMemoryBM25Index().search(LexicalSearchRequest(query="policy", top_k=1))


def test_remove_existing_chunk_updates_state() -> None:
    first = _chunk(text="policy alpha", chunk_index=0)
    second = _chunk(text="policy beta gamma", chunk_index=1)
    index = _index_with(first, second)

    removed = index.remove(first.chunk_id)

    assert removed is True
    assert index.size == 1
    assert index.get(first.chunk_id) is None
    assert index.average_document_length == pytest.approx(3.0)


def test_remove_absent_chunk_returns_false() -> None:
    index = _index_with(_chunk(text="policy"))

    assert index.remove(uuid4()) is False


def test_remove_updates_corpus_statistics() -> None:
    first = _chunk(text="zanzibar policy", chunk_index=0)
    second = _chunk(text="policy beta", chunk_index=1)
    index = _index_with(first, second)
    index.remove(first.chunk_id)

    response = index.search(LexicalSearchRequest(query="zanzibar", top_k=5))

    assert response.results == ()


def test_removed_chunk_no_longer_appears() -> None:
    first = _chunk(text="leave policy", chunk_index=0)
    second = _chunk(text="expense policy", chunk_index=1)
    index = _index_with(first, second)
    index.remove(first.chunk_id)

    response = index.search(LexicalSearchRequest(query="leave", top_k=5))

    assert response.results == ()


def test_remove_resets_average_length_when_empty() -> None:
    chunk = _chunk(text="policy")
    index = _index_with(chunk)

    index.remove(chunk.chunk_id)

    assert index.size == 0
    assert index.average_document_length == 0.0


def _index_with(*chunks: DocumentChunk) -> InMemoryBM25Index:
    index = InMemoryBM25Index()
    index.add(tuple(chunks))
    return index


def _source() -> DocumentSource:
    return DocumentSource(
        filename="sample.pdf",
        media_type="application/pdf",
        size_bytes=128,
    )


def _chunk(
    *,
    text: str,
    chunk_id: UUID | None = None,
    source: DocumentSource | None = None,
    page_number: int = 1,
    chunk_index: int = 0,
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id or uuid4(),
        document_id=uuid4(),
        source=source or _source(),
        page_number=page_number,
        chunk_index=chunk_index,
        text=text,
    )
