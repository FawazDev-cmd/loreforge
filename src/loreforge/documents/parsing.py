"""Framework-independent PDF parsing into LoreForge document contracts."""

from io import BytesIO
from uuid import UUID

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from loreforge.documents.models import DocumentPage, DocumentSource, ParsedDocument


class PdfParsingError(ValueError):
    """Raised when PDF bytes cannot be parsed into document pages."""


def parse_pdf(
    *,
    document_id: UUID,
    source: DocumentSource,
    content: bytes,
) -> ParsedDocument:
    """Parse PDF bytes into an ordered page-aware document."""
    if not content:
        msg = "PDF content must not be empty"
        raise PdfParsingError(msg)

    try:
        reader = PdfReader(BytesIO(content))
    except PyPdfError as error:
        msg = "PDF content is malformed or unreadable"
        raise PdfParsingError(msg) from error

    if reader.is_encrypted:
        try:
            decrypt_result = reader.decrypt("")
        except PyPdfError as error:
            msg = "PDF is encrypted"
            raise PdfParsingError(msg) from error

        if not decrypt_result:
            msg = "PDF is encrypted"
            raise PdfParsingError(msg)

    try:
        page_count = len(reader.pages)
    except PyPdfError as error:
        msg = "PDF content is malformed or unreadable"
        raise PdfParsingError(msg) from error

    if page_count == 0:
        msg = "PDF must contain at least one page"
        raise PdfParsingError(msg)

    pages: list[DocumentPage] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text()
        except PyPdfError as error:
            msg = "PDF page text is unreadable"
            raise PdfParsingError(msg) from error

        if text is None or not text.strip():
            msg = "PDF page has no extractable text"
            raise PdfParsingError(msg)

        pages.append(DocumentPage(page_number=index, text=text))

    return ParsedDocument(
        document_id=document_id,
        source=source,
        pages=tuple(pages),
    )
