"""Framework-independent reranking models."""

from dataclasses import dataclass
from math import isfinite
from uuid import UUID

from loreforge.retrieval.hybrid_models import HybridSearchResult


@dataclass(frozen=True, slots=True)
class RerankingRequest:
    """Query-passage pair to score for one candidate chunk."""

    item_id: UUID
    query: str
    passage: str

    def __post_init__(self) -> None:
        if not self.query.strip():
            msg = "query must not be empty"
            raise ValueError(msg)

        if not self.passage.strip():
            msg = "passage must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RerankingScore:
    """Reranker score for one requested item."""

    item_id: UUID
    score: float

    def __post_init__(self) -> None:
        if type(self.score) is not float:
            msg = "score must be a float"
            raise ValueError(msg)

        if not isfinite(self.score):
            msg = "score must be finite"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RerankedSearchResult:
    """Hybrid retrieval result with final reranker score and rank."""

    hybrid_result: HybridSearchResult
    reranker_score: float
    rank: int

    def __post_init__(self) -> None:
        if type(self.reranker_score) is not float:
            msg = "reranker_score must be a float"
            raise ValueError(msg)

        if not isfinite(self.reranker_score):
            msg = "reranker_score must be finite"
            raise ValueError(msg)

        if self.rank < 1:
            msg = "rank must be greater than or equal to 1"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RerankedSearchResponse:
    """Ordered reranked evidence for the original question."""

    question: str
    results: tuple[RerankedSearchResult, ...]

    def __post_init__(self) -> None:
        if not self.question.strip():
            msg = "question must not be empty"
            raise ValueError(msg)

        ranks = tuple(result.rank for result in self.results)
        expected_ranks = tuple(range(1, len(self.results) + 1))
        if ranks != expected_ranks:
            msg = "result ranks must be one-based and sequential"
            raise ValueError(msg)

        chunk_ids = tuple(
            result.hybrid_result.chunk.chunk_id for result in self.results
        )
        if len(set(chunk_ids)) != len(chunk_ids):
            msg = "result chunk IDs must be unique"
            raise ValueError(msg)
