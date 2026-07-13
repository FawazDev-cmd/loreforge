import pytest

from loreforge.documents.upload import (
    MAX_UPLOAD_SIZE_BYTES,
    PDF_MEDIA_TYPE,
    UnsupportedDocumentError,
    validate_pdf_upload,
)


def test_validate_pdf_upload_accepts_valid_pdf_metadata_and_content() -> None:
    upload = validate_pdf_upload(
        filename="handbook.pdf",
        media_type=PDF_MEDIA_TYPE,
        content=b"%PDF-1.7\ncontent",
    )

    assert upload.filename == "handbook.pdf"
    assert upload.media_type == PDF_MEDIA_TYPE
    assert upload.size_bytes == len(b"%PDF-1.7\ncontent")


def test_validate_pdf_upload_rejects_empty_filename() -> None:
    with pytest.raises(ValueError, match="filename"):
        validate_pdf_upload(
            filename="",
            media_type=PDF_MEDIA_TYPE,
            content=b"%PDF-1.7\ncontent",
        )


def test_validate_pdf_upload_rejects_whitespace_only_filename() -> None:
    with pytest.raises(ValueError, match="filename"):
        validate_pdf_upload(
            filename="   ",
            media_type=PDF_MEDIA_TYPE,
            content=b"%PDF-1.7\ncontent",
        )


def test_validate_pdf_upload_reduces_forward_slash_path_to_basename() -> None:
    upload = validate_pdf_upload(
        filename="../../reports/handbook.pdf",
        media_type=PDF_MEDIA_TYPE,
        content=b"%PDF-1.7\ncontent",
    )

    assert upload.filename == "handbook.pdf"


def test_validate_pdf_upload_reduces_backslash_path_to_basename() -> None:
    upload = validate_pdf_upload(
        filename=r"C:\private\report.pdf",
        media_type=PDF_MEDIA_TYPE,
        content=b"%PDF-1.7\ncontent",
    )

    assert upload.filename == "report.pdf"


def test_validate_pdf_upload_accepts_uppercase_pdf_extension() -> None:
    upload = validate_pdf_upload(
        filename="handbook.PDF",
        media_type=PDF_MEDIA_TYPE,
        content=b"%PDF-1.7\ncontent",
    )

    assert upload.filename == "handbook.PDF"


def test_validate_pdf_upload_rejects_non_pdf_extension() -> None:
    with pytest.raises(UnsupportedDocumentError, match="extension"):
        validate_pdf_upload(
            filename="handbook.txt",
            media_type=PDF_MEDIA_TYPE,
            content=b"%PDF-1.7\ncontent",
        )


def test_validate_pdf_upload_rejects_wrong_media_type() -> None:
    with pytest.raises(UnsupportedDocumentError, match="media type"):
        validate_pdf_upload(
            filename="handbook.pdf",
            media_type="text/plain",
            content=b"%PDF-1.7\ncontent",
        )


def test_validate_pdf_upload_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="empty"):
        validate_pdf_upload(
            filename="handbook.pdf",
            media_type=PDF_MEDIA_TYPE,
            content=b"",
        )


def test_validate_pdf_upload_rejects_invalid_pdf_signature() -> None:
    with pytest.raises(UnsupportedDocumentError, match="signature"):
        validate_pdf_upload(
            filename="handbook.pdf",
            media_type=PDF_MEDIA_TYPE,
            content=b"not a pdf",
        )


def test_validate_pdf_upload_rejects_content_over_size_limit() -> None:
    content = b"%PDF-" + b"x" * (MAX_UPLOAD_SIZE_BYTES + 1 - len(b"%PDF-"))

    with pytest.raises(ValueError, match="maximum size"):
        validate_pdf_upload(
            filename="handbook.pdf",
            media_type=PDF_MEDIA_TYPE,
            content=content,
        )


def test_validate_pdf_upload_accepts_content_exactly_at_size_limit() -> None:
    content = b"%PDF-" + b"x" * (MAX_UPLOAD_SIZE_BYTES - len(b"%PDF-"))

    upload = validate_pdf_upload(
        filename="handbook.pdf",
        media_type=PDF_MEDIA_TYPE,
        content=content,
    )

    assert upload.size_bytes == MAX_UPLOAD_SIZE_BYTES
