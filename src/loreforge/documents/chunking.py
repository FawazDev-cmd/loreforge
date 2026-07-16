"""Deterministic page-bounded chunking for parsed documents."""

import re
from dataclasses import dataclass
from uuid import UUID, uuid5

from loreforge.documents.models import DocumentChunk, ParsedDocument

LOREFORGE_CHUNK_NAMESPACE = UUID("f1fe1b74-7a44-4d6a-9c83-b1b9174f8f55")

_SENTENCE_BOUNDARY_PATTERN = re.compile(r"[.!?]\s+")


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    chunk_size: int = 1000
    chunk_overlap: int = 150

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            msg = "chunk_size must be greater than zero"
            raise ValueError(msg)

        if self.chunk_overlap < 0:
            msg = "chunk_overlap must be greater than or equal to 0"
            raise ValueError(msg)

        if self.chunk_overlap >= self.chunk_size:
            msg = "chunk_overlap must be smaller than chunk_size"
            raise ValueError(msg)


def chunk_document(
    document: ParsedDocument,
    config: ChunkingConfig = ChunkingConfig(),
) -> tuple[DocumentChunk, ...]:
    """Split document pages into deterministic citation-aware chunks."""
    chunks: list[DocumentChunk] = []

    for page in document.pages:
        start = 0
        previous_start = -1

        while start < len(page.text):
            end_limit = min(start + config.chunk_size, len(page.text))
            end = _select_chunk_end(
                text=page.text,
                start=start,
                end_limit=end_limit,
                chunk_size=config.chunk_size,
            )
            chunk_text = page.text[start:end].strip()

            if chunk_text:
                chunk_index = len(chunks)
                chunks.append(
                    DocumentChunk(
                        chunk_id=_chunk_id(
                            document_id=document.document_id,
                            page_number=page.page_number,
                            chunk_index=chunk_index,
                            text=chunk_text,
                            config=config,
                        ),
                        document_id=document.document_id,
                        source=document.source,
                        page_number=page.page_number,
                        chunk_index=chunk_index,
                        text=chunk_text,
                    )
                )

            if end_limit == len(page.text):
                break

            next_start = max(end - config.chunk_overlap, start + 1)
            if next_start <= previous_start:
                next_start = previous_start + 1

            previous_start = start
            start = next_start

    return tuple(chunks)


def _select_chunk_end(
    *,
    text: str,
    start: int,
    end_limit: int,
    chunk_size: int,
) -> int:
    if end_limit == len(text):
        return end_limit

    minimum_boundary = start + max(1, chunk_size // 2)

    paragraph_end = _latest_boundary(text, "\n\n", start, end_limit)
    if paragraph_end is not None and paragraph_end >= minimum_boundary:
        return paragraph_end

    newline_end = _latest_boundary(text, "\n", start, end_limit)
    if newline_end is not None and newline_end >= minimum_boundary:
        return newline_end

    sentence_end = _latest_sentence_boundary(text, start, end_limit)
    if sentence_end is not None and sentence_end >= minimum_boundary:
        return sentence_end

    space_end = _latest_boundary(text, " ", start, end_limit)
    if space_end is not None and space_end >= minimum_boundary:
        return space_end

    return end_limit


def _latest_boundary(
    text: str,
    boundary: str,
    start: int,
    end_limit: int,
) -> int | None:
    boundary_index = text.rfind(boundary, start, end_limit)
    if boundary_index == -1:
        return None
    return boundary_index + len(boundary)


def _latest_sentence_boundary(text: str, start: int, end_limit: int) -> int | None:
    sentence_end: int | None = None
    for match in _SENTENCE_BOUNDARY_PATTERN.finditer(text, start, end_limit):
        sentence_end = match.end()
    return sentence_end


def _chunk_id(
    *,
    document_id: UUID,
    page_number: int,
    chunk_index: int,
    text: str,
    config: ChunkingConfig,
) -> UUID:
    uuid_name = (
        f"document_id={document_id}|"
        f"page_number={page_number}|"
        f"chunk_index={chunk_index}|"
        f"chunk_size={config.chunk_size}|"
        f"chunk_overlap={config.chunk_overlap}|"
        f"text={text}"
    )
    return uuid5(LOREFORGE_CHUNK_NAMESPACE, uuid_name)
