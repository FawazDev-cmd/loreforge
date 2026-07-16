from uuid import UUID, uuid4

import pytest

from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.embeddings import EmbeddedChunk, EmbeddingVector
from loreforge.vector_index import InMemoryVectorIndex, VectorIndexError


def test_index_initial_state() -> None:
    index = InMemoryVectorIndex()

    assert index.size == 0
    assert index.dimensions is None
    assert index.get(uuid4()) is None


def test_add_one_item() -> None:
    item = _embedded(values=(1.0, 0.0))
    index = InMemoryVectorIndex()

    index.add((item,))

    stored = index.get(item.chunk.chunk_id)
    assert index.size == 1
    assert index.dimensions == 2
    assert stored is not None
    assert stored.chunk == item.chunk
    assert stored.vector == item.vector


def test_add_multiple_items() -> None:
    items = (
        _embedded(values=(1.0, 0.0), chunk_index=0),
        _embedded(values=(0.0, 1.0), chunk_index=1),
    )
    index = InMemoryVectorIndex()

    index.add(items)

    assert index.size == 2
    assert index.dimensions == 2
    assert [index.get(item.chunk.chunk_id).chunk for item in items] == [  # type: ignore[union-attr]
        item.chunk for item in items
    ]


def test_add_preserves_full_chunk_provenance() -> None:
    source = DocumentSource(
        filename="policy.pdf",
        media_type="application/pdf",
        size_bytes=512,
    )
    chunk = _chunk(
        source=source,
        page_number=7,
        chunk_index=3,
        text="Policy chunk text",
    )
    item = _embedded(chunk=chunk, values=(1.0, 0.0))
    index = InMemoryVectorIndex()

    index.add((item,))

    stored = index.get(chunk.chunk_id)
    assert stored is not None
    assert stored.chunk.document_id == chunk.document_id
    assert stored.chunk.source == source
    assert stored.chunk.page_number == 7
    assert stored.chunk.chunk_index == 3
    assert stored.chunk.text == "Policy chunk text"


def test_add_rejects_duplicate_existing_id() -> None:
    item = _embedded(values=(1.0, 0.0))
    index = InMemoryVectorIndex()
    index.add((item,))

    with pytest.raises(VectorIndexError, match="already exists"):
        index.add((item,))


def test_add_rejects_duplicate_id_within_batch() -> None:
    chunk_id = uuid4()
    items = (
        _embedded(values=(1.0, 0.0), chunk_id=chunk_id, chunk_index=0),
        _embedded(values=(0.0, 1.0), chunk_id=chunk_id, chunk_index=1),
    )
    index = InMemoryVectorIndex()

    with pytest.raises(VectorIndexError, match="duplicate"):
        index.add(items)

    assert index.size == 0
    assert index.dimensions is None


def test_add_rejects_dimension_mismatch() -> None:
    index = InMemoryVectorIndex()
    index.add((_embedded(values=(1.0, 0.0)),))

    with pytest.raises(VectorIndexError, match="dimensions"):
        index.add((_embedded(values=(1.0, 0.0, 0.0), chunk_index=1),))


def test_failed_batch_leaves_index_unchanged() -> None:
    existing = _embedded(values=(1.0, 0.0), chunk_index=0)
    duplicate = _embedded(
        values=(0.0, 1.0),
        chunk_id=existing.chunk.chunk_id,
        chunk_index=1,
    )
    new_item = _embedded(values=(0.5, 0.5), chunk_index=2)
    index = InMemoryVectorIndex()
    index.add((existing,))

    with pytest.raises(VectorIndexError):
        index.add((duplicate, new_item))

    assert index.size == 1
    assert index.get(existing.chunk.chunk_id) is not None
    assert index.get(new_item.chunk.chunk_id) is None


def test_failed_empty_index_batch_leaves_dimensions_unset() -> None:
    index = InMemoryVectorIndex()

    with pytest.raises(VectorIndexError, match="dimensions"):
        index.add(
            (
                _embedded(values=(1.0, 0.0), chunk_index=0),
                _embedded(values=(1.0, 0.0, 0.0), chunk_index=1),
            )
        )

    assert index.size == 0
    assert index.dimensions is None


def test_add_rejects_empty_tuple() -> None:
    with pytest.raises(VectorIndexError, match="items"):
        InMemoryVectorIndex().add(())


def test_search_exact_match_ranks_first() -> None:
    matching = _embedded(values=(1.0, 0.0), chunk_index=0)
    other = _embedded(values=(0.0, 1.0), chunk_index=1)
    index = _index_with(matching, other)

    results = index.search(query_vector=(1.0, 0.0), top_k=2)

    assert results[0].indexed.chunk == matching.chunk
    assert results[0].score == pytest.approx(1.0)


def test_search_orders_results_by_descending_score() -> None:
    best = _embedded(values=(1.0, 0.0), chunk_index=0)
    middle = _embedded(values=(0.5, 0.5), chunk_index=1)
    worst = _embedded(values=(-1.0, 0.0), chunk_index=2)
    index = _index_with(worst, middle, best)

    results = index.search(query_vector=(1.0, 0.0), top_k=3)

    assert [result.indexed.chunk for result in results] == [
        best.chunk,
        middle.chunk,
        worst.chunk,
    ]


def test_search_assigns_one_based_sequential_ranks() -> None:
    index = _index_with(
        _embedded(values=(1.0, 0.0), chunk_index=0),
        _embedded(values=(0.0, 1.0), chunk_index=1),
    )

    results = index.search(query_vector=(1.0, 0.0), top_k=2)

    assert [result.rank for result in results] == [1, 2]


def test_search_top_k_limits_results() -> None:
    index = _index_with(
        _embedded(values=(1.0, 0.0), chunk_index=0),
        _embedded(values=(0.0, 1.0), chunk_index=1),
    )

    results = index.search(query_vector=(1.0, 0.0), top_k=1)

    assert len(results) == 1


def test_search_top_k_above_size_returns_all_items() -> None:
    index = _index_with(
        _embedded(values=(1.0, 0.0), chunk_index=0),
        _embedded(values=(0.0, 1.0), chunk_index=1),
    )

    results = index.search(query_vector=(1.0, 0.0), top_k=99)

    assert len(results) == 2


def test_search_applies_deterministic_uuid_tie_break() -> None:
    later_id = UUID("00000000-0000-0000-0000-000000000002")
    earlier_id = UUID("00000000-0000-0000-0000-000000000001")
    later = _embedded(values=(1.0, 0.0), chunk_id=later_id, chunk_index=0)
    earlier = _embedded(values=(1.0, 0.0), chunk_id=earlier_id, chunk_index=1)
    index = _index_with(later, earlier)

    results = index.search(query_vector=(1.0, 0.0), top_k=2)

    assert [result.indexed.chunk.chunk_id for result in results] == [
        earlier_id,
        later_id,
    ]


def test_search_rejects_query_dimension_mismatch() -> None:
    index = _index_with(_embedded(values=(1.0, 0.0)))

    with pytest.raises(VectorIndexError, match="dimensions"):
        index.search(query_vector=(1.0,), top_k=1)


def test_search_rejects_empty_index() -> None:
    with pytest.raises(VectorIndexError, match="empty"):
        InMemoryVectorIndex().search(query_vector=(1.0,), top_k=1)


@pytest.mark.parametrize("top_k", [0, -1])
def test_search_rejects_non_positive_top_k(top_k: int) -> None:
    index = _index_with(_embedded(values=(1.0, 0.0)))

    with pytest.raises(VectorIndexError, match="top_k"):
        index.search(query_vector=(1.0, 0.0), top_k=top_k)


def test_search_rejects_zero_magnitude_query() -> None:
    index = _index_with(_embedded(values=(1.0, 0.0)))

    with pytest.raises(VectorIndexError, match="query"):
        index.search(query_vector=(0.0, 0.0), top_k=1)


def test_search_result_is_tuple() -> None:
    index = _index_with(_embedded(values=(1.0, 0.0)))

    result = index.search(query_vector=(1.0, 0.0), top_k=1)

    assert isinstance(result, tuple)


def test_search_does_not_mutate_index() -> None:
    item = _embedded(values=(1.0, 0.0))
    index = _index_with(item)

    index.search(query_vector=(1.0, 0.0), top_k=1)

    assert index.size == 1
    assert index.get(item.chunk.chunk_id) is not None


def test_remove_existing_item() -> None:
    item = _embedded(values=(1.0, 0.0))
    index = _index_with(item)

    removed = index.remove(item.chunk.chunk_id)

    assert removed is True
    assert index.get(item.chunk.chunk_id) is None


def test_remove_missing_item_returns_false() -> None:
    index = _index_with(_embedded(values=(1.0, 0.0)))

    assert index.remove(uuid4()) is False


def test_remove_updates_size() -> None:
    first = _embedded(values=(1.0, 0.0), chunk_index=0)
    second = _embedded(values=(0.0, 1.0), chunk_index=1)
    index = _index_with(first, second)

    index.remove(first.chunk.chunk_id)

    assert index.size == 1


def test_remove_keeps_dimensions_while_items_exist() -> None:
    first = _embedded(values=(1.0, 0.0), chunk_index=0)
    second = _embedded(values=(0.0, 1.0), chunk_index=1)
    index = _index_with(first, second)

    index.remove(first.chunk.chunk_id)

    assert index.dimensions == 2


def test_remove_resets_dimensions_after_last_item() -> None:
    item = _embedded(values=(1.0, 0.0))
    index = _index_with(item)

    index.remove(item.chunk.chunk_id)

    assert index.size == 0
    assert index.dimensions is None


def test_repeated_searches_return_equal_results() -> None:
    index = _index_with(
        _embedded(values=(1.0, 0.0), chunk_index=0),
        _embedded(values=(0.0, 1.0), chunk_index=1),
    )

    first = index.search(query_vector=(1.0, 0.0), top_k=2)
    second = index.search(query_vector=(1.0, 0.0), top_k=2)

    assert first == second


def test_indexes_with_same_data_produce_equal_rankings() -> None:
    items = (
        _embedded(values=(1.0, 0.0), chunk_index=0),
        _embedded(values=(0.0, 1.0), chunk_index=1),
    )
    first = _index_with(*items)
    second = _index_with(*items)

    first_results = first.search(query_vector=(1.0, 0.0), top_k=2)
    second_results = second.search(query_vector=(1.0, 0.0), top_k=2)

    assert [result.indexed.chunk.chunk_id for result in first_results] == [
        result.indexed.chunk.chunk_id for result in second_results
    ]


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
    source: DocumentSource | None = None,
    page_number: int = 1,
    chunk_index: int = 0,
    text: str = "Chunk text",
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id or uuid4(),
        document_id=uuid4(),
        source=source or _source(),
        page_number=page_number,
        chunk_index=chunk_index,
        text=text,
    )


def _embedded(
    *,
    values: tuple[float, ...] = (1.0,),
    chunk: DocumentChunk | None = None,
    chunk_id: UUID | None = None,
    source: DocumentSource | None = None,
    page_number: int = 1,
    chunk_index: int = 0,
    text: str = "Chunk text",
) -> EmbeddedChunk:
    resolved_chunk = chunk or _chunk(
        chunk_id=chunk_id,
        source=source,
        page_number=page_number,
        chunk_index=chunk_index,
        text=text,
    )
    return EmbeddedChunk(
        chunk=resolved_chunk,
        vector=EmbeddingVector(item_id=resolved_chunk.chunk_id, values=values),
    )
