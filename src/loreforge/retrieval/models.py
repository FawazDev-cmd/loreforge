"""Framework-independent semantic retrieval models."""

from dataclasses import dataclass

from loreforge.vector_index import VectorSearchResult


@dataclass(frozen=True, slots=True)
class SemanticSearchRequest:
    """User question and result limit for semantic retrieval."""

    question: str
    top_k: int

    def __post_init__(self) -> None:
        if not self.question.strip():
            msg = "question must not be empty"
            raise ValueError(msg)

        if self.top_k <= 0:
            msg = "top_k must be greater than zero"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SemanticSearchResponse:
    """Ranked semantic search results for the original question."""

    question: str
    results: tuple[VectorSearchResult, ...]
