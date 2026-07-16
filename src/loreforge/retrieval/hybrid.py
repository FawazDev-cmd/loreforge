"""Hybrid retrieval using Reciprocal Rank Fusion."""

from dataclasses import dataclass
from uuid import UUID

from loreforge.documents.models import DocumentChunk
from loreforge.embeddings import QueryEmbeddingProvider
from loreforge.retrieval.bm25 import InMemoryBM25Index
from loreforge.retrieval.hybrid_models import (
    LEXICAL_STRATEGY,
    SEMANTIC_STRATEGY,
    HybridSearchRequest,
    HybridSearchResponse,
    HybridSearchResult,
    RetrievalContribution,
)
from loreforge.retrieval.lexical_models import LexicalSearchRequest, LexicalSearchResult
from loreforge.retrieval.models import SemanticSearchRequest
from loreforge.retrieval.semantic import semantic_search
from loreforge.vector_index import InMemoryVectorIndex, VectorSearchResult


class HybridRetrievalError(ValueError):
    """Raised when hybrid retrieval cannot safely fuse result lists."""


@dataclass(frozen=True, slots=True)
class _FusionCandidate:
    chunk_id: UUID
    chunk: DocumentChunk
    semantic: RetrievalContribution | None = None
    lexical: RetrievalContribution | None = None


def reciprocal_rank_fusion(
    *,
    semantic_results: tuple[VectorSearchResult, ...],
    lexical_results: tuple[LexicalSearchResult, ...],
    top_k: int,
    rrf_k: int = 60,
) -> tuple[HybridSearchResult, ...]:
    """Fuse semantic and lexical rankings with 1 / (rrf_k + rank)."""
    if top_k <= 0:
        msg = "top_k must be greater than zero"
        raise ValueError(msg)

    if rrf_k <= 0:
        msg = "rrf_k must be greater than zero"
        raise ValueError(msg)

    candidates: dict[UUID, _FusionCandidate] = {}

    for semantic_result in semantic_results:
        chunk = semantic_result.indexed.chunk
        contribution = RetrievalContribution(
            strategy=SEMANTIC_STRATEGY,
            rank=semantic_result.rank,
            score=semantic_result.score,
        )
        candidates[chunk.chunk_id] = _merge_candidate(
            candidates.get(chunk.chunk_id),
            chunk=chunk,
            semantic=contribution,
        )

    for lexical_result in lexical_results:
        chunk = lexical_result.chunk
        contribution = RetrievalContribution(
            strategy=LEXICAL_STRATEGY,
            rank=lexical_result.rank,
            score=lexical_result.score,
        )
        candidates[chunk.chunk_id] = _merge_candidate(
            candidates.get(chunk.chunk_id),
            chunk=chunk,
            lexical=contribution,
        )

    scored_candidates = tuple(
        (
            candidate,
            _rrf_score(candidate.semantic, rrf_k)
            + _rrf_score(candidate.lexical, rrf_k),
        )
        for candidate in candidates.values()
    )
    ranked = sorted(
        scored_candidates,
        key=lambda item: (-item[1], str(item[0].chunk_id)),
    )[:top_k]

    return tuple(
        HybridSearchResult(
            chunk=candidate.chunk,
            fused_score=fused_score,
            rank=rank,
            contributions=_ordered_contributions(candidate),
        )
        for rank, (candidate, fused_score) in enumerate(ranked, start=1)
    )


def hybrid_search(
    *,
    request: HybridSearchRequest,
    semantic_provider: QueryEmbeddingProvider,
    vector_index: InMemoryVectorIndex,
    lexical_index: InMemoryBM25Index,
    rrf_k: int = 60,
) -> HybridSearchResponse:
    """Run semantic and lexical retrieval, then fuse their result lists."""
    semantic_response = semantic_search(
        request=SemanticSearchRequest(
            question=request.question,
            top_k=request.semantic_top_k,
        ),
        provider=semantic_provider,
        index=vector_index,
    )
    lexical_response = lexical_index.search(
        LexicalSearchRequest(
            query=request.question,
            top_k=request.lexical_top_k,
        )
    )
    results = reciprocal_rank_fusion(
        semantic_results=semantic_response.results,
        lexical_results=lexical_response.results,
        top_k=request.top_k,
        rrf_k=rrf_k,
    )

    return HybridSearchResponse(question=request.question, results=results)


def _merge_candidate(
    existing: _FusionCandidate | None,
    *,
    chunk: DocumentChunk,
    semantic: RetrievalContribution | None = None,
    lexical: RetrievalContribution | None = None,
) -> _FusionCandidate:
    chunk_id = chunk.chunk_id
    if existing is None:
        return _FusionCandidate(
            chunk_id=chunk_id,
            chunk=chunk,
            semantic=semantic,
            lexical=lexical,
        )

    if existing.chunk != chunk:
        msg = "conflicting chunk provenance for fused result"
        raise HybridRetrievalError(msg)

    return _FusionCandidate(
        chunk_id=existing.chunk_id,
        chunk=existing.chunk,
        semantic=semantic or existing.semantic,
        lexical=lexical or existing.lexical,
    )


def _rrf_score(contribution: RetrievalContribution | None, rrf_k: int) -> float:
    if contribution is None:
        return 0.0

    return 1.0 / (rrf_k + contribution.rank)


def _ordered_contributions(
    candidate: _FusionCandidate,
) -> tuple[RetrievalContribution, ...]:
    contributions: list[RetrievalContribution] = []
    if candidate.semantic is not None:
        contributions.append(candidate.semantic)
    if candidate.lexical is not None:
        contributions.append(candidate.lexical)

    return tuple(contributions)
