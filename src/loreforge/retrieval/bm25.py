"""Deterministic in-memory BM25 lexical index."""

from collections import Counter
from dataclasses import dataclass
from math import isfinite, log
from uuid import UUID

from loreforge.documents.models import DocumentChunk
from loreforge.retrieval.lexical_models import (
    LexicalSearchRequest,
    LexicalSearchResponse,
    LexicalSearchResult,
)
from loreforge.retrieval.tokenization import tokenize


class BM25IndexError(ValueError):
    """Raised when BM25 index contract validation fails."""


@dataclass(frozen=True, slots=True)
class BM25Config:
    """BM25 tuning constants."""

    k1: float = 1.5
    b: float = 0.75

    def __post_init__(self) -> None:
        if type(self.k1) is not float:
            msg = "k1 must be a float"
            raise ValueError(msg)

        if type(self.b) is not float:
            msg = "b must be a float"
            raise ValueError(msg)

        if not isfinite(self.k1):
            msg = "k1 must be finite"
            raise ValueError(msg)

        if not isfinite(self.b):
            msg = "b must be finite"
            raise ValueError(msg)

        if self.k1 <= 0.0:
            msg = "k1 must be greater than zero"
            raise ValueError(msg)

        if not 0.0 <= self.b <= 1.0:
            msg = "b must be between zero and one"
            raise ValueError(msg)


class InMemoryBM25Index:
    """Exact in-memory BM25 index over document chunks."""

    def __init__(self, config: BM25Config = BM25Config()) -> None:
        self._config = config
        self._chunks: dict[UUID, DocumentChunk] = {}
        self._term_frequencies: dict[UUID, Counter[str]] = {}
        self._document_lengths: dict[UUID, int] = {}
        self._document_frequencies: Counter[str] = Counter()
        self._average_document_length = 0.0

    @property
    def size(self) -> int:
        """Return the number of indexed chunks."""
        return len(self._chunks)

    @property
    def average_document_length(self) -> float:
        """Return the average tokenized chunk length."""
        return self._average_document_length

    def add(self, chunks: tuple[DocumentChunk, ...]) -> None:
        """Atomically add document chunks to the BM25 index."""
        if not chunks:
            msg = "chunks must contain at least one chunk"
            raise BM25IndexError(msg)

        chunk_ids = tuple(chunk.chunk_id for chunk in chunks)
        if len(set(chunk_ids)) != len(chunk_ids):
            msg = "batch contains duplicate chunk IDs"
            raise BM25IndexError(msg)

        existing_ids = set(self._chunks)
        if any(chunk_id in existing_ids for chunk_id in chunk_ids):
            msg = "chunk ID already exists in index"
            raise BM25IndexError(msg)

        prepared = tuple((chunk, Counter(tokenize(chunk.text))) for chunk in chunks)

        for chunk, term_frequencies in prepared:
            self._chunks[chunk.chunk_id] = chunk
            self._term_frequencies[chunk.chunk_id] = term_frequencies
            self._document_lengths[chunk.chunk_id] = sum(term_frequencies.values())
            self._document_frequencies.update(term_frequencies.keys())

        self._recalculate_average_document_length()

    def get(self, chunk_id: UUID) -> DocumentChunk | None:
        """Return an indexed chunk by ID when present."""
        return self._chunks.get(chunk_id)

    def remove(self, chunk_id: UUID) -> bool:
        """Remove a chunk and update corpus statistics."""
        if chunk_id not in self._chunks:
            return False

        term_frequencies = self._term_frequencies[chunk_id]
        for term in term_frequencies:
            self._document_frequencies[term] -= 1
            if self._document_frequencies[term] <= 0:
                del self._document_frequencies[term]

        del self._chunks[chunk_id]
        del self._term_frequencies[chunk_id]
        del self._document_lengths[chunk_id]
        self._recalculate_average_document_length()

        return True

    def search(self, request: LexicalSearchRequest) -> LexicalSearchResponse:
        """Search with BM25 using positive IDF: log(1 + (N - df + .5)/(df + .5))."""
        if not self._chunks:
            msg = "cannot search an empty BM25 index"
            raise BM25IndexError(msg)

        query_terms = tuple(dict.fromkeys(tokenize(request.query)))
        scored = tuple(
            (chunk_id, score)
            for chunk_id in self._chunks
            if (score := self._score_chunk(chunk_id, query_terms)) > 0.0
        )
        ranked = sorted(scored, key=lambda item: (-item[1], str(item[0])))[
            : request.top_k
        ]

        results = tuple(
            LexicalSearchResult(
                chunk=self._chunks[chunk_id],
                score=score,
                rank=rank,
            )
            for rank, (chunk_id, score) in enumerate(ranked, start=1)
        )

        return LexicalSearchResponse(query=request.query, results=results)

    def _score_chunk(self, chunk_id: UUID, query_terms: tuple[str, ...]) -> float:
        score = 0.0
        document_count = len(self._chunks)
        document_length = self._document_lengths[chunk_id]
        term_frequencies = self._term_frequencies[chunk_id]

        for term in query_terms:
            term_frequency = term_frequencies.get(term, 0)
            if term_frequency == 0:
                continue

            document_frequency = self._document_frequencies[term]
            idf = log(
                1.0
                + (document_count - document_frequency + 0.5)
                / (document_frequency + 0.5)
            )
            denominator = term_frequency + self._config.k1 * (
                1.0
                - self._config.b
                + self._config.b * document_length / self._average_document_length
            )
            score += idf * (term_frequency * (self._config.k1 + 1.0)) / denominator

        return float(score)

    def _recalculate_average_document_length(self) -> None:
        if not self._document_lengths:
            self._average_document_length = 0.0
            return

        self._average_document_length = float(
            sum(self._document_lengths.values()) / len(self._document_lengths)
        )
