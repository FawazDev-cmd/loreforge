"""Public document contracts for LoreForge."""

from loreforge.documents.models import DocumentPage, DocumentSource, ParsedDocument
from loreforge.documents.parsing import PdfParsingError, parse_pdf
from loreforge.documents.upload import (
    MAX_UPLOAD_SIZE_BYTES,
    PDF_MEDIA_TYPE,
    PDF_SIGNATURE,
    UnsupportedDocumentError,
    ValidatedUpload,
    validate_pdf_upload,
)

__all__ = [
    "DocumentPage",
    "DocumentSource",
    "MAX_UPLOAD_SIZE_BYTES",
    "PDF_MEDIA_TYPE",
    "PDF_SIGNATURE",
    "PdfParsingError",
    "ParsedDocument",
    "UnsupportedDocumentError",
    "ValidatedUpload",
    "parse_pdf",
    "validate_pdf_upload",
]
