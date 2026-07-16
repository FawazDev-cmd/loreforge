"""Framework-independent hybrid retrieval models."""

from dataclasses import dataclass
from math import isfinite

from loreforge.documents.models import DocumentChunk

SEMANTIC_STRATEGY = "semantic"
LEXICAL_STRATEGY = "lexical"
_STRATEGY_ORDER = {
    SEMANTIC_STRATEGY: 0,
    LEXICAL_STRATEGY: 1,
}


@dataclass(frozen=True, slots=True)
class RetrievalContribution:
    """A retrieval strategy's original contribution to a fused result."""

    strategy: str
    rank: int
    score: float

    def __post_init__(self) -> None:
        if not self.strategy.strip():
            msg = "strategy must not be empty"
            raise ValueError(msg)

        if self.rank < 1:
            msg = "rank must be greater than or equal to 1"
            raise ValueError(msg)

        if type(self.score) is not float:
            msg = "score must be a float"
            raise ValueError(msg)

        if not isfinite(self.score):
            msg = "score must be finite"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class HybridSearchResult:
    """Deduplicated retrieval evidence with fused score and contributions."""

    chunk: DocumentChunk
    fused_score: float
    rank: int
    contributions: tuple[RetrievalContribution, ...]

    def __post_init__(self) -> None:
        if type(self.fused_score) is not float:
            msg = "fused_score must be a float"
            raise ValueError(msg)

        if not isfinite(self.fused_score):
            msg = "fused_score must be finite"
            raise ValueError(msg)

        if self.fused_score <= 0.0:
            msg = "fused_score must be greater than zero"
            raise ValueError(msg)

        if self.rank < 1:
            msg = "rank must be greater than or equal to 1"
            raise ValueError(msg)

        if not self.contributions:
            msg = "contributions must contain at least one contribution"
            raise ValueError(msg)

        strategies = tuple(contribution.strategy for contribution in self.contributions)
        if len(set(strategies)) != len(strategies):
            msg = "contribution strategies must be unique"
            raise ValueError(msg)

        if strategies != tuple(sorted(strategies, key=_contribution_sort_key)):
            msg = "contributions must be ordered semantic then lexical"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class HybridSearchRequest:
    """Query and candidate limits for hybrid retrieval."""

    question: str
    top_k: int = 5
    semantic_top_k: int = 10
    lexical_top_k: int = 10

    def __post_init__(self) -> None:
        if not self.question.strip():
            msg = "question must not be empty"
            raise ValueError(msg)

        if self.top_k <= 0:
            msg = "top_k must be greater than zero"
            raise ValueError(msg)

        if self.semantic_top_k <= 0:
            msg = "semantic_top_k must be greater than zero"
            raise ValueError(msg)

        if self.lexical_top_k <= 0:
            msg = "lexical_top_k must be greater than zero"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class HybridSearchResponse:
    """Final ordered hybrid retrieval results for the original question."""

    question: str
    results: tuple[HybridSearchResult, ...]

    def __post_init__(self) -> None:
        if not self.question.strip():
            msg = "question must not be empty"
            raise ValueError(msg)

        ranks = tuple(result.rank for result in self.results)
        expected_ranks = tuple(range(1, len(self.results) + 1))
        if ranks != expected_ranks:
            msg = "result ranks must be one-based and sequential"
            raise ValueError(msg)

        chunk_ids = tuple(result.chunk.chunk_id for result in self.results)
        if len(set(chunk_ids)) != len(chunk_ids):
            msg = "result chunk IDs must be unique"
            raise ValueError(msg)


def _contribution_sort_key(strategy: str) -> int:
    return _STRATEGY_ORDER.get(strategy, len(_STRATEGY_ORDER))
