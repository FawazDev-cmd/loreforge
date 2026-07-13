"""Framework-independent validation for uploaded document bytes."""

from dataclasses import dataclass
from posixpath import basename

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
PDF_MEDIA_TYPE = "application/pdf"
PDF_SIGNATURE = b"%PDF-"


class UnsupportedDocumentError(ValueError):
    """Raised when upload metadata or content is not a supported document type."""


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    """Validated upload metadata and content size."""

    filename: str
    media_type: str
    size_bytes: int


def validate_pdf_upload(
    *,
    filename: str | None,
    media_type: str | None,
    content: bytes,
) -> ValidatedUpload:
    """Validate a PDF upload without parsing or persisting it."""
    safe_filename = _safe_basename(filename)

    if not safe_filename.lower().endswith(".pdf"):
        msg = "unsupported filename extension"
        raise UnsupportedDocumentError(msg)

    if media_type != PDF_MEDIA_TYPE:
        msg = "unsupported media type"
        raise UnsupportedDocumentError(msg)

    size_bytes = len(content)

    if size_bytes == 0:
        msg = "uploaded file must not be empty"
        raise ValueError(msg)

    if size_bytes > MAX_UPLOAD_SIZE_BYTES:
        msg = "uploaded file exceeds maximum size"
        raise ValueError(msg)

    if not content.startswith(PDF_SIGNATURE):
        msg = "invalid PDF signature"
        raise UnsupportedDocumentError(msg)

    return ValidatedUpload(
        filename=safe_filename,
        media_type=PDF_MEDIA_TYPE,
        size_bytes=size_bytes,
    )


def _safe_basename(filename: str | None) -> str:
    if filename is None or not filename.strip():
        msg = "filename must not be empty"
        raise ValueError(msg)

    safe_filename = basename(filename.replace("\\", "/"))

    if not safe_filename.strip():
        msg = "filename must not be empty"
        raise ValueError(msg)

    return safe_filename
