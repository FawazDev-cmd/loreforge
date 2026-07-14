from dataclasses import FrozenInstanceError
from io import BytesIO
from uuid import uuid4

import pytest
from pypdf import PdfWriter

from loreforge.documents import DocumentSource, PdfParsingError, parse_pdf


def test_parse_pdf_produces_page_aware_parsed_document() -> None:
    document_id = uuid4()
    source = DocumentSource(
        filename="two-page-sample.pdf",
        media_type="application/pdf",
        size_bytes=len(_two_page_pdf()),
    )

    parsed_document = parse_pdf(
        document_id=document_id,
        source=source,
        content=_two_page_pdf(),
    )

    assert parsed_document.document_id == document_id
    assert parsed_document.source == source
    assert len(parsed_document.pages) == 2
    assert [page.page_number for page in parsed_document.pages] == [1, 2]
    assert "LoreForge first page" in parsed_document.pages[0].text
    assert "LoreForge second page" in parsed_document.pages[1].text


def test_parse_pdf_resulting_models_remain_immutable() -> None:
    parsed_document = parse_pdf(
        document_id=uuid4(),
        source=DocumentSource(
            filename="two-page-sample.pdf",
            media_type="application/pdf",
            size_bytes=len(_two_page_pdf()),
        ),
        content=_two_page_pdf(),
    )

    with pytest.raises(FrozenInstanceError):
        parsed_document.pages = ()

    with pytest.raises(FrozenInstanceError):
        parsed_document.pages[0].text = "Changed text."


def test_parse_pdf_rejects_empty_content() -> None:
    with pytest.raises(PdfParsingError, match="empty"):
        parse_pdf(document_id=uuid4(), source=_source(size_bytes=1), content=b"")


def test_parse_pdf_rejects_malformed_bytes() -> None:
    with pytest.raises(PdfParsingError, match="malformed|unreadable"):
        parse_pdf(
            document_id=uuid4(),
            source=_source(size_bytes=len(b"not a pdf")),
            content=b"not a pdf",
        )


def test_parse_pdf_rejects_encrypted_pdf() -> None:
    content = _encrypted_pdf()

    with pytest.raises(PdfParsingError, match="encrypted"):
        parse_pdf(
            document_id=uuid4(),
            source=_source(size_bytes=len(content)),
            content=content,
        )


def test_parse_pdf_rejects_pdf_with_zero_pages() -> None:
    content = _zero_page_pdf()

    with pytest.raises(PdfParsingError, match="page"):
        parse_pdf(
            document_id=uuid4(),
            source=_source(size_bytes=len(content)),
            content=content,
        )


def test_parse_pdf_rejects_page_without_extractable_text() -> None:
    content = _blank_page_pdf()

    with pytest.raises(PdfParsingError, match="extractable text"):
        parse_pdf(
            document_id=uuid4(),
            source=_source(size_bytes=len(content)),
            content=content,
        )


def _source(*, size_bytes: int) -> DocumentSource:
    return DocumentSource(
        filename="sample.pdf",
        media_type="application/pdf",
        size_bytes=size_bytes,
    )


def _two_page_pdf() -> bytes:
    return _build_text_pdf(
        (
            "LoreForge first page synthetic text.",
            "LoreForge second page synthetic text.",
        )
    )


def _blank_page_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _zero_page_pdf() -> bytes:
    writer = PdfWriter()
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt(user_password="secret")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _build_text_pdf(page_texts: tuple[str, ...]) -> bytes:
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        _pages_object(len(page_texts)),
    ]

    font_object_number = 3 + len(page_texts)
    first_content_object_number = font_object_number + 1

    for index, text in enumerate(page_texts, start=1):
        content_object_number = first_content_object_number + index - 1
        objects.append(_page_object(content_object_number, font_object_number))

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for text in page_texts:
        objects.append(_content_stream(text))

    return _serialize_pdf(objects)


def _pages_object(page_count: int) -> bytes:
    kids = " ".join(f"{number} 0 R" for number in range(3, 3 + page_count))
    return f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode("ascii")


def _page_object(content_object_number: int, font_object_number: int) -> bytes:
    return (
        b"<< /Type /Page /Parent 2 0 R /Resources "
        + f"<< /Font << /F1 {font_object_number} 0 R >> >> ".encode("ascii")
        + b"/MediaBox [0 0 612 792] "
        + f"/Contents {content_object_number} 0 R >>".encode("ascii")
    )


def _content_stream(text: str) -> bytes:
    content = (f"BT\n/F1 24 Tf\n72 720 Td\n({_escape_pdf_text(text)}) Tj\nET\n").encode(
        "ascii"
    )
    return (
        b"<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"endstream"
    )


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _serialize_pdf(objects: list[bytes]) -> bytes:
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]

    for object_number, payload in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode("ascii"))
        pdf.extend(payload)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)
