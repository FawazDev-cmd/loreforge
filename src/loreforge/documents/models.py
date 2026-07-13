"""Framework-independent document representation contracts."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DocumentSource:
    """Source metadata for an uploaded document."""

    filename: str
    media_type: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not self.filename.strip():
            msg = "filename must not be empty"
            raise ValueError(msg)

        if not self.media_type.strip():
            msg = "media_type must not be empty"
            raise ValueError(msg)

        if self.size_bytes <= 0:
            msg = "size_bytes must be greater than zero"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class DocumentPage:
    """One-based page text extracted from a document."""

    page_number: int
    text: str

    def __post_init__(self) -> None:
        if self.page_number < 1:
            msg = "page_number must be greater than or equal to 1"
            raise ValueError(msg)

        if not self.text.strip():
            msg = "text must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """Parsed document pages with stable document identity and source metadata."""

    document_id: UUID
    source: DocumentSource
    pages: tuple[DocumentPage, ...]

    def __post_init__(self) -> None:
        if not self.pages:
            msg = "pages must contain at least one page"
            raise ValueError(msg)

        page_numbers = tuple(page.page_number for page in self.pages)

        if len(set(page_numbers)) != len(page_numbers):
            msg = "page numbers must be unique"
            raise ValueError(msg)

        if page_numbers != tuple(sorted(page_numbers)):
            msg = "pages must be ordered by ascending page number"
            raise ValueError(msg)
