"""Framework-independent lexical retrieval models."""

from dataclasses import dataclass
from math import isfinite

from loreforge.documents.models import DocumentChunk


@dataclass(frozen=True, slots=True)
class LexicalSearchRequest:
    """Query text and result limit for lexical retrieval."""

    query: str
    top_k: int

    def __post_init__(self) -> None:
        if not self.query.strip():
            msg = "query must not be empty"
            raise ValueError(msg)

        if self.top_k <= 0:
            msg = "top_k must be greater than zero"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class LexicalSearchResult:
    """Ranked lexical search hit with BM25 score."""

    chunk: DocumentChunk
    score: float
    rank: int

    def __post_init__(self) -> None:
        if type(self.score) is not float:
            msg = "score must be a float"
            raise ValueError(msg)

        if not isfinite(self.score):
            msg = "score must be finite"
            raise ValueError(msg)

        if self.score < 0.0:
            msg = "score must be greater than or equal to zero"
            raise ValueError(msg)

        if self.rank < 1:
            msg = "rank must be greater than or equal to 1"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class LexicalSearchResponse:
    """Ordered lexical retrieval results for the original query."""

    query: str
    results: tuple[LexicalSearchResult, ...]

    def __post_init__(self) -> None:
        if not self.query.strip():
            msg = "query must not be empty"
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
