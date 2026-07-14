"""Deterministic text normalization for parsed document pages."""

import re

from loreforge.documents.models import DocumentPage, ParsedDocument

_HORIZONTAL_WHITESPACE_PATTERN = re.compile(r"[^\S\n]+")
_THREE_OR_MORE_NEWLINES_PATTERN = re.compile(r"\n{3,}")


class TextNormalizationError(ValueError):
    """Raised when parsed document text cannot be normalized safely."""


def normalize_document(document: ParsedDocument) -> ParsedDocument:
    """Normalize page text while preserving document and page boundaries."""
    normalized_pages: list[DocumentPage] = []

    for page in document.pages:
        normalized_text = _normalize_text(page.text)
        if not normalized_text.strip():
            msg = f"page {page.page_number} is empty after normalization"
            raise TextNormalizationError(msg)

        normalized_pages.append(
            DocumentPage(page_number=page.page_number, text=normalized_text)
        )

    return ParsedDocument(
        document_id=document.document_id,
        source=document.source,
        pages=tuple(normalized_pages),
    )


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [
        _HORIZONTAL_WHITESPACE_PATTERN.sub(" ", line).strip()
        for line in text.split("\n")
    ]
    text = "\n".join(lines)
    text = _THREE_OR_MORE_NEWLINES_PATTERN.sub("\n\n", text)
    return text.strip()
