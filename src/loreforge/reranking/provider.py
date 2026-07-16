"""Reranker provider protocol."""

from typing import Protocol, runtime_checkable

from loreforge.reranking.models import RerankingRequest, RerankingScore


@runtime_checkable
class RerankerProvider(Protocol):
    """Provider that scores ordered query-passage reranking requests."""

    def score(
        self,
        requests: tuple[RerankingRequest, ...],
    ) -> tuple[RerankingScore, ...]:
        """Return one ordered score for each request."""
        ...
