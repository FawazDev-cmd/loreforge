"""Evidence-context construction for grounded generation prompts."""

from dataclasses import dataclass
from math import isfinite
from re import fullmatch
from uuid import UUID

from loreforge.reranking import RerankedSearchResult


class EvidenceContextError(ValueError):
    """Raised when reranked evidence cannot form a valid prompt context."""


@dataclass(frozen=True, slots=True)
class EvidenceContextConfig:
    """Character budget for rendered evidence supplied to a future model."""

    max_characters: int = 12000

    def __post_init__(self) -> None:
        if type(self.max_characters) is not int:
            msg = "max_characters must be an integer"
            raise ValueError(msg)

        if self.max_characters <= 0:
            msg = "max_characters must be greater than zero"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """Structured provenance for one rendered evidence block."""

    citation_id: str
    chunk_id: UUID
    document_id: UUID
    filename: str
    page_number: int
    text: str
    reranker_score: float
    retrieval_rank: int

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

        if not self.text.strip():
            msg = "text must not be empty"
            raise ValueError(msg)

        if type(self.reranker_score) is not float:
            msg = "reranker_score must be a float"
            raise ValueError(msg)

        if not isfinite(self.reranker_score):
            msg = "reranker_score must be finite"
            raise ValueError(msg)

        if self.retrieval_rank < 1:
            msg = "retrieval_rank must be greater than or equal to 1"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class EvidenceContext:
    """Rendered evidence plus structured provenance for prompt construction."""

    items: tuple[EvidenceItem, ...]
    rendered_text: str
    total_characters: int
    truncated: bool

    def __post_init__(self) -> None:
        if not self.items:
            msg = "items must contain at least one evidence item"
            raise ValueError(msg)

        citation_ids = tuple(item.citation_id for item in self.items)
        if len(set(citation_ids)) != len(citation_ids):
            msg = "citation IDs must be unique"
            raise ValueError(msg)

        expected_citation_ids = tuple(
            f"S{index}" for index in range(1, len(self.items) + 1)
        )
        if citation_ids != expected_citation_ids:
            msg = "citation IDs must be sequential in supplied order"
            raise ValueError(msg)

        chunk_ids = tuple(item.chunk_id for item in self.items)
        if len(set(chunk_ids)) != len(chunk_ids):
            msg = "chunk IDs must be unique"
            raise ValueError(msg)

        if not self.rendered_text.strip():
            msg = "rendered_text must not be empty"
            raise ValueError(msg)

        if self.total_characters != len(self.rendered_text):
            msg = "total_characters must equal rendered_text length"
            raise ValueError(msg)

        truncated: object = self.truncated
        if type(truncated) is not bool:
            msg = "truncated must be a boolean"
            raise ValueError(msg)


def build_evidence_context(
    *,
    candidates: tuple[RerankedSearchResult, ...],
    config: EvidenceContextConfig = EvidenceContextConfig(),
) -> EvidenceContext:
    """Build a deterministic, budgeted evidence context from reranked results."""
    if not candidates:
        msg = "at least one reranked candidate is required"
        raise EvidenceContextError(msg)

    items: list[EvidenceItem] = []
    blocks: list[str] = []

    for index, candidate in enumerate(candidates, start=1):
        chunk = candidate.hybrid_result.chunk
        citation_id = f"S{index}"
        item = EvidenceItem(
            citation_id=citation_id,
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            filename=chunk.source.filename,
            page_number=chunk.page_number,
            text=chunk.text,
            reranker_score=candidate.reranker_score,
            retrieval_rank=candidate.rank,
        )
        block = _render_evidence_block(item)
        next_rendered = block if not blocks else f"{_join_blocks(blocks)}\n\n{block}"

        if len(next_rendered) > config.max_characters:
            if not blocks:
                msg = "highest-ranked evidence item exceeds the character budget"
                raise EvidenceContextError(msg)
            return _context_from_blocks(items, blocks, truncated=True)

        items.append(item)
        blocks.append(block)

    return _context_from_blocks(items, blocks, truncated=False)


def _render_evidence_block(item: EvidenceItem) -> str:
    return (
        f"[{item.citation_id}]\n"
        f"Source: {item.filename}\n"
        f"Page: {item.page_number}\n"
        "Content:\n"
        f"{item.text}"
    )


def _context_from_blocks(
    items: list[EvidenceItem], blocks: list[str], *, truncated: bool
) -> EvidenceContext:
    rendered_text = _join_blocks(blocks)
    return EvidenceContext(
        items=tuple(items),
        rendered_text=rendered_text,
        total_characters=len(rendered_text),
        truncated=truncated,
    )


def _join_blocks(blocks: list[str]) -> str:
    return "\n\n".join(blocks)
