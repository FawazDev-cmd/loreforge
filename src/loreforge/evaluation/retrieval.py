"""Deterministic ranked retrieval evaluation."""

from uuid import UUID

from loreforge.evaluation.models import RetrievalMetrics


def evaluate_retrieval(
    *,
    relevant_chunk_ids: tuple[UUID, ...],
    retrieved_chunk_ids: tuple[UUID, ...],
    k: int,
) -> RetrievalMetrics:
    """Evaluate ranked chunk IDs with hit-rate, precision, recall, and MRR."""
    _validate_uuid_tuple(relevant_chunk_ids, "relevant_chunk_ids", allow_empty=False)
    _validate_uuid_tuple(retrieved_chunk_ids, "retrieved_chunk_ids", allow_empty=True)

    k_object: object = k
    if type(k_object) is not int:
        msg = "k must be an integer"
        raise ValueError(msg)

    if k <= 0:
        msg = "k must be greater than zero"
        raise ValueError(msg)

    relevant = set(relevant_chunk_ids)
    considered = retrieved_chunk_ids[:k]
    matches = sum(1 for chunk_id in considered if chunk_id in relevant)

    hit_rate = 1.0 if matches else 0.0
    precision = float(matches / len(considered)) if considered else 0.0
    recall = float(matches / len(relevant_chunk_ids))
    reciprocal_rank = _reciprocal_rank(retrieved_chunk_ids, relevant)

    return RetrievalMetrics(
        k=k,
        hit_rate=float(hit_rate),
        precision=float(precision),
        recall=float(recall),
        reciprocal_rank=float(reciprocal_rank),
    )


def _validate_uuid_tuple(
    values: tuple[UUID, ...], name: str, *, allow_empty: bool
) -> None:
    if not allow_empty and not values:
        msg = f"{name} must contain at least one ID"
        raise ValueError(msg)

    if len(set(values)) != len(values):
        msg = f"{name} must contain unique values"
        raise ValueError(msg)


def _reciprocal_rank(
    retrieved_chunk_ids: tuple[UUID, ...], relevant: set[UUID]
) -> float:
    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if chunk_id in relevant:
            return float(1.0 / rank)
    return 0.0
