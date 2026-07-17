"""Grounded-answer models for generation orchestration."""

from dataclasses import dataclass
from math import isfinite
from re import fullmatch
from uuid import UUID

from loreforge.generation.evidence import EvidenceContext
from loreforge.reranking import RerankedSearchResult


@dataclass(frozen=True, slots=True)
class GroundedGenerationRequest:
    """Inputs and limits for one grounded-answer generation run."""

    question: str
    candidates: tuple[RerankedSearchResult, ...]
    evidence_max_characters: int = 12000
    max_output_tokens: int = 800
    temperature: float = 0.0

    def __post_init__(self) -> None:
        if not self.question.strip():
            msg = "question must not be empty"
            raise ValueError(msg)

        if not self.candidates:
            msg = "candidates must contain at least one candidate"
            raise ValueError(msg)

        chunk_ids = tuple(
            candidate.hybrid_result.chunk.chunk_id for candidate in self.candidates
        )
        if len(set(chunk_ids)) != len(chunk_ids):
            msg = "candidate chunk IDs must be unique"
            raise ValueError(msg)

        ranks = tuple(candidate.rank for candidate in self.candidates)
        expected_ranks = tuple(range(1, len(self.candidates) + 1))
        if ranks != expected_ranks:
            msg = "candidate ranks must be one-based and sequential"
            raise ValueError(msg)

        evidence_max_characters: object = self.evidence_max_characters
        if type(evidence_max_characters) is not int:
            msg = "evidence_max_characters must be an integer"
            raise ValueError(msg)

        if self.evidence_max_characters <= 0:
            msg = "evidence_max_characters must be greater than zero"
            raise ValueError(msg)

        max_output_tokens: object = self.max_output_tokens
        if type(max_output_tokens) is not int:
            msg = "max_output_tokens must be an integer"
            raise ValueError(msg)

        if self.max_output_tokens <= 0:
            msg = "max_output_tokens must be greater than zero"
            raise ValueError(msg)

        temperature: object = self.temperature
        if type(temperature) is not float:
            msg = "temperature must be a float"
            raise ValueError(msg)

        if not isfinite(self.temperature):
            msg = "temperature must be finite"
            raise ValueError(msg)

        if not 0.0 <= self.temperature <= 2.0:
            msg = "temperature must be between 0.0 and 2.0"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Source evidence made available to the model during generation."""

    citation_id: str
    document_id: UUID
    chunk_id: UUID
    filename: str
    page_number: int

    def __post_init__(self) -> None:
        if fullmatch(r"S[1-9][0-9]*", self.citation_id) is None:
            msg = "citation_id must match S followed by a positive integer"
            raise ValueError(msg)

        if not self.filename.strip():
            msg = "filename must not be empty"
            raise ValueError(msg)

        if self.page_number < 1:
            msg = "page_number must be greater than or equal to 1"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    """Raw generated answer with evidence provenance and validation state."""

    question: str
    answer_text: str
    sources: tuple[SourceReference, ...]
    evidence: EvidenceContext
    provider_model: str
    finish_reason: str | None
    citations_validated: bool

    def __post_init__(self) -> None:
        if not self.question.strip():
            msg = "question must not be empty"
            raise ValueError(msg)

        if not self.answer_text.strip():
            msg = "answer_text must not be empty"
            raise ValueError(msg)

        if not self.sources:
            msg = "sources must contain at least one source"
            raise ValueError(msg)

        citation_ids = tuple(source.citation_id for source in self.sources)
        if len(set(citation_ids)) != len(citation_ids):
            msg = "source citation IDs must be unique"
            raise ValueError(msg)

        expected_citation_ids = tuple(
            f"S{index}" for index in range(1, len(self.sources) + 1)
        )
        if citation_ids != expected_citation_ids:
            msg = "source citation IDs must be sequential in supplied order"
            raise ValueError(msg)

        chunk_ids = tuple(source.chunk_id for source in self.sources)
        if len(set(chunk_ids)) != len(chunk_ids):
            msg = "source chunk IDs must be unique"
            raise ValueError(msg)

        expected_sources = tuple(
            SourceReference(
                citation_id=item.citation_id,
                document_id=item.document_id,
                chunk_id=item.chunk_id,
                filename=item.filename,
                page_number=item.page_number,
            )
            for item in self.evidence.items
        )
        if self.sources != expected_sources:
            msg = "sources must match evidence items in order"
            raise ValueError(msg)

        if not self.provider_model.strip():
            msg = "provider_model must not be empty"
            raise ValueError(msg)

        if self.finish_reason is not None and not self.finish_reason.strip():
            msg = "finish_reason must not be empty when provided"
            raise ValueError(msg)

        citations_validated: object = self.citations_validated
        if type(citations_validated) is not bool:
            msg = "citations_validated must be a boolean"
            raise ValueError(msg)
