from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from loreforge.documents import (
    DocumentPage,
    DocumentSource,
    ParsedDocument,
    TextNormalizationError,
    normalize_document,
)


def test_normalize_document_normalizes_whitespace_deterministically() -> None:
    document = _document(
        (
            DocumentPage(
                page_number=1,
                text=(
                    "  First\t\tline  \r\n"
                    "Second    line\r"
                    "Third\t line\n\n\n\n"
                    "  Fourth line  "
                ),
            ),
        )
    )

    normalized = normalize_document(document)

    assert normalized.pages[0].text == (
        "First line\nSecond line\nThird line\n\nFourth line"
    )


def test_normalize_document_preserves_structure_and_text_content() -> None:
    document = _document(
        (
            DocumentPage(
                page_number=1,
                text="Title: Café Résumé!\nNext Line.\n\nNASA Stays Uppercase.",
            ),
        )
    )

    normalized = normalize_document(document)

    assert normalized.pages[0].text == (
        "Title: Café Résumé!\nNext Line.\n\nNASA Stays Uppercase."
    )


def test_normalize_document_preserves_page_boundaries() -> None:
    document = _document(
        (
            DocumentPage(page_number=1, text="  Page   one  "),
            DocumentPage(page_number=2, text="\tPage   two\t"),
        )
    )

    normalized = normalize_document(document)

    assert [page.page_number for page in normalized.pages] == [1, 2]
    assert [page.text for page in normalized.pages] == ["Page one", "Page two"]


def test_normalize_document_preserves_document_metadata_and_order() -> None:
    document_id = uuid4()
    source = _source()
    document = ParsedDocument(
        document_id=document_id,
        source=source,
        pages=(
            DocumentPage(page_number=3, text=" Third   page "),
            DocumentPage(page_number=5, text=" Fifth   page "),
        ),
    )

    normalized = normalize_document(document)

    assert normalized.document_id == document_id
    assert normalized.source == source
    assert [page.page_number for page in normalized.pages] == [3, 5]
    assert len(normalized.pages) == 2


def test_normalize_document_does_not_mutate_input_document() -> None:
    document = _document((DocumentPage(page_number=1, text="  Original   text  "),))

    normalized = normalize_document(document)

    assert document.pages[0].text == "  Original   text  "
    assert normalized.pages[0].text == "Original text"
    assert normalized is not document
    assert normalized.pages[0] is not document.pages[0]


def test_normalize_document_returns_immutable_models() -> None:
    normalized = normalize_document(
        _document((DocumentPage(page_number=1, text="Immutable text"),))
    )

    with pytest.raises(FrozenInstanceError):
        normalized.pages = ()

    with pytest.raises(FrozenInstanceError):
        normalized.pages[0].text = "Changed text"


def test_normalize_document_is_idempotent() -> None:
    document = _document(
        (
            DocumentPage(page_number=1, text="  First\tline\n\n\nSecond   line  "),
            DocumentPage(page_number=2, text="Already normalized"),
        )
    )

    assert normalize_document(normalize_document(document)) == normalize_document(
        document
    )


def test_normalize_document_rejects_page_that_becomes_empty() -> None:
    empty_after_normalization = DocumentPage(page_number=2, text="Temporary text")
    object.__setattr__(empty_after_normalization, "text", " \t \r\n \n\t ")
    document = _document(
        (
            DocumentPage(page_number=1, text="Valid page"),
            empty_after_normalization,
        )
    )

    with pytest.raises(TextNormalizationError, match="page 2"):
        normalize_document(document)


def _document(pages: tuple[DocumentPage, ...]) -> ParsedDocument:
    return ParsedDocument(document_id=uuid4(), source=_source(), pages=pages)


def _source() -> DocumentSource:
    return DocumentSource(
        filename="sample.pdf",
        media_type="application/pdf",
        size_bytes=1024,
    )
