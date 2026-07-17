from uuid import UUID

import pytest

from loreforge.evaluation import evaluate_retrieval

ID1 = UUID("00000000-0000-0000-0000-000000000001")
ID2 = UUID("00000000-0000-0000-0000-000000000002")
ID3 = UUID("00000000-0000-0000-0000-000000000003")
ID4 = UUID("00000000-0000-0000-0000-000000000004")


def test_relevant_result_at_rank_one() -> None:
    metrics = evaluate_retrieval(
        relevant_chunk_ids=(ID1,), retrieved_chunk_ids=(ID1, ID2), k=2
    )

    assert metrics.hit_rate == 1.0
    assert metrics.precision == 0.5
    assert metrics.recall == 1.0
    assert metrics.reciprocal_rank == 1.0


def test_relevant_result_below_rank_one() -> None:
    metrics = evaluate_retrieval(
        relevant_chunk_ids=(ID2,), retrieved_chunk_ids=(ID1, ID2), k=2
    )

    assert metrics.reciprocal_rank == 0.5


def test_no_relevant_result() -> None:
    metrics = evaluate_retrieval(
        relevant_chunk_ids=(ID3,), retrieved_chunk_ids=(ID1, ID2), k=2
    )

    assert metrics.hit_rate == 0.0
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.reciprocal_rank == 0.0


def test_multiple_relevant_results() -> None:
    metrics = evaluate_retrieval(
        relevant_chunk_ids=(ID1, ID2), retrieved_chunk_ids=(ID1, ID2, ID3), k=3
    )

    assert metrics.precision == pytest.approx(2 / 3)
    assert metrics.recall == 1.0


def test_hit_rate_at_k() -> None:
    metrics = evaluate_retrieval(
        relevant_chunk_ids=(ID2,), retrieved_chunk_ids=(ID1, ID2), k=2
    )

    assert metrics.hit_rate == 1.0


def test_relevant_result_outside_k_does_not_affect_top_k_metrics() -> None:
    metrics = evaluate_retrieval(
        relevant_chunk_ids=(ID3,), retrieved_chunk_ids=(ID1, ID2, ID3), k=2
    )

    assert metrics.hit_rate == 0.0
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0


def test_relevant_result_outside_k_affects_reciprocal_rank() -> None:
    metrics = evaluate_retrieval(
        relevant_chunk_ids=(ID3,), retrieved_chunk_ids=(ID1, ID2, ID3), k=2
    )

    assert metrics.reciprocal_rank == pytest.approx(1 / 3)


def test_precision_divides_by_actual_results_considered() -> None:
    metrics = evaluate_retrieval(
        relevant_chunk_ids=(ID1, ID2), retrieved_chunk_ids=(ID1,), k=5
    )

    assert metrics.precision == 1.0


def test_fewer_than_k_results() -> None:
    metrics = evaluate_retrieval(
        relevant_chunk_ids=(ID2,), retrieved_chunk_ids=(ID1,), k=5
    )

    assert metrics.precision == 0.0


def test_empty_retrieved_tuple() -> None:
    metrics = evaluate_retrieval(relevant_chunk_ids=(ID1,), retrieved_chunk_ids=(), k=3)

    assert metrics.precision == 0.0
    assert metrics.reciprocal_rank == 0.0


def test_k_of_one() -> None:
    metrics = evaluate_retrieval(
        relevant_chunk_ids=(ID2,), retrieved_chunk_ids=(ID1, ID2), k=1
    )

    assert metrics.hit_rate == 0.0


def test_k_greater_than_result_count() -> None:
    metrics = evaluate_retrieval(
        relevant_chunk_ids=(ID1,), retrieved_chunk_ids=(ID1, ID2), k=10
    )

    assert metrics.k == 10
    assert metrics.precision == 0.5


def test_duplicate_relevant_ids_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        evaluate_retrieval(
            relevant_chunk_ids=(ID1, ID1), retrieved_chunk_ids=(ID1,), k=1
        )


def test_duplicate_retrieved_ids_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        evaluate_retrieval(
            relevant_chunk_ids=(ID1,), retrieved_chunk_ids=(ID1, ID1), k=1
        )


def test_empty_relevant_ids_rejected() -> None:
    with pytest.raises(ValueError, match="relevant_chunk_ids"):
        evaluate_retrieval(relevant_chunk_ids=(), retrieved_chunk_ids=(ID1,), k=1)


@pytest.mark.parametrize("k", [0, -1, True])
def test_invalid_k_rejected(k: int) -> None:
    with pytest.raises(ValueError, match="k"):
        evaluate_retrieval(relevant_chunk_ids=(ID1,), retrieved_chunk_ids=(ID1,), k=k)  # type: ignore[arg-type]


def test_repeated_evaluation_is_deterministic() -> None:
    kwargs = {"relevant_chunk_ids": (ID2,), "retrieved_chunk_ids": (ID1, ID2), "k": 2}

    assert evaluate_retrieval(**kwargs) == evaluate_retrieval(**kwargs)


def test_inputs_remain_unchanged() -> None:
    relevant = (ID1,)
    retrieved = (ID1, ID2)
    before = (relevant, retrieved)

    evaluate_retrieval(relevant_chunk_ids=relevant, retrieved_chunk_ids=retrieved, k=2)

    assert (relevant, retrieved) == before
