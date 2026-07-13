from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from loreforge.documents import DocumentPage, DocumentSource, ParsedDocument


def test_document_source_accepts_valid_metadata() -> None:
    source = DocumentSource(
        filename="handbook.pdf",
        media_type="application/pdf",
        size_bytes=1024,
    )

    assert source.filename == "handbook.pdf"
    assert source.media_type == "application/pdf"
    assert source.size_bytes == 1024


def test_document_page_accepts_valid_page_text() -> None:
    page = DocumentPage(page_number=1, text="Company handbook introduction.")

    assert page.page_number == 1
    assert page.text == "Company handbook introduction."


def test_parsed_document_accepts_valid_pages() -> None:
    document_id = uuid4()
    source = DocumentSource(
        filename="handbook.pdf",
        media_type="application/pdf",
        size_bytes=1024,
    )
    pages = (
        DocumentPage(page_number=1, text="First page."),
        DocumentPage(page_number=2, text="Second page."),
    )

    document = ParsedDocument(document_id=document_id, source=source, pages=pages)

    assert document.document_id == document_id
    assert document.source == source
    assert document.pages == pages


def test_document_source_rejects_empty_filename() -> None:
    with pytest.raises(ValueError, match="filename"):
        DocumentSource(filename="", media_type="application/pdf", size_bytes=1024)


def test_document_source_rejects_whitespace_only_filename() -> None:
    with pytest.raises(ValueError, match="filename"):
        DocumentSource(filename="   ", media_type="application/pdf", size_bytes=1024)


def test_document_source_rejects_empty_media_type() -> None:
    with pytest.raises(ValueError, match="media_type"):
        DocumentSource(filename="handbook.pdf", media_type="", size_bytes=1024)


def test_document_source_rejects_non_positive_size() -> None:
    with pytest.raises(ValueError, match="size_bytes"):
        DocumentSource(
            filename="handbook.pdf", media_type="application/pdf", size_bytes=0
        )


def test_document_page_rejects_page_number_below_one() -> None:
    with pytest.raises(ValueError, match="page_number"):
        DocumentPage(page_number=0, text="Page text.")


def test_document_page_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="text"):
        DocumentPage(page_number=1, text="")


def test_document_page_rejects_whitespace_only_text() -> None:
    with pytest.raises(ValueError, match="text"):
        DocumentPage(page_number=1, text="   ")


def test_parsed_document_rejects_no_pages() -> None:
    source = DocumentSource(
        filename="handbook.pdf",
        media_type="application/pdf",
        size_bytes=1024,
    )

    with pytest.raises(ValueError, match="pages"):
        ParsedDocument(document_id=uuid4(), source=source, pages=())


def test_parsed_document_rejects_duplicate_page_numbers() -> None:
    source = DocumentSource(
        filename="handbook.pdf",
        media_type="application/pdf",
        size_bytes=1024,
    )
    pages = (
        DocumentPage(page_number=1, text="First copy."),
        DocumentPage(page_number=1, text="Second copy."),
    )

    with pytest.raises(ValueError, match="unique"):
        ParsedDocument(document_id=uuid4(), source=source, pages=pages)


def test_parsed_document_rejects_incorrectly_ordered_page_numbers() -> None:
    source = DocumentSource(
        filename="handbook.pdf",
        media_type="application/pdf",
        size_bytes=1024,
    )
    pages = (
        DocumentPage(page_number=2, text="Second page."),
        DocumentPage(page_number=1, text="First page."),
    )

    with pytest.raises(ValueError, match="ordered"):
        ParsedDocument(document_id=uuid4(), source=source, pages=pages)


def test_document_contracts_are_immutable() -> None:
    source = DocumentSource(
        filename="handbook.pdf",
        media_type="application/pdf",
        size_bytes=1024,
    )
    page = DocumentPage(page_number=1, text="First page.")
    document = ParsedDocument(document_id=uuid4(), source=source, pages=(page,))

    with pytest.raises(FrozenInstanceError):
        source.filename = "renamed.pdf"

    with pytest.raises(FrozenInstanceError):
        page.text = "Changed text."

    with pytest.raises(FrozenInstanceError):
        document.pages = ()
