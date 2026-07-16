"""Reranking pipeline for hybrid retrieval candidates."""

from loreforge.reranking.models import (
    RerankedSearchResponse,
    RerankedSearchResult,
    RerankingRequest,
)
from loreforge.reranking.provider import RerankerProvider
from loreforge.retrieval import HybridSearchResult


class RerankingPipelineError(ValueError):
    """Raised when reranker output violates the ordered batch contract."""


def rerank_hybrid_results(
    *,
    question: str,
    candidates: tuple[HybridSearchResult, ...],
    provider: RerankerProvider,
    top_k: int,
) -> RerankedSearchResponse:
    """Rerank hybrid retrieval candidates with a provider score."""
    if not question.strip():
        msg = "question must not be empty"
        raise ValueError(msg)

    if top_k <= 0:
        msg = "top_k must be greater than zero"
        raise ValueError(msg)

    if not candidates:
        return RerankedSearchResponse(question=question, results=())

    requests = tuple(
        RerankingRequest(
            item_id=candidate.chunk.chunk_id,
            query=question,
            passage=candidate.chunk.text,
        )
        for candidate in candidates
    )
    scores = provider.score(requests)

    if len(scores) != len(candidates):
        msg = "provider returned a different number of scores than candidates"
        raise RerankingPipelineError(msg)

    paired: list[tuple[HybridSearchResult, float]] = []
    for candidate, score in zip(candidates, scores, strict=True):
        if score.item_id != candidate.chunk.chunk_id:
            msg = "provider returned scores out of candidate order"
            raise RerankingPipelineError(msg)

        paired.append((candidate, score.score))

    ranked = sorted(
        paired,
        key=lambda item: (-item[1], item[0].rank, str(item[0].chunk.chunk_id)),
    )[:top_k]

    return RerankedSearchResponse(
        question=question,
        results=tuple(
            RerankedSearchResult(
                hybrid_result=hybrid_result,
                reranker_score=score,
                rank=rank,
            )
            for rank, (hybrid_result, score) in enumerate(ranked, start=1)
        ),
    )
