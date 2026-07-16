from dataclasses import FrozenInstanceError
from io import BytesIO
from uuid import uuid4

import pytest
from pypdf import PdfWriter

from loreforge.documents import (
    ChunkingConfig,
    DocumentSource,
    IngestionResult,
    PdfParsingError,
    ingest_pdf,
)


def test_ingest_pdf_returns_result_for_valid_multi_page_pdf() -> None:
    content = _text_pdf(
        (
            "First page has enough text for ingestion.",
            "Second page keeps provenance intact.",
        )
    )
    document_id = uuid4()
    source = _source(size_bytes=len(content))

    result = ingest_pdf(
        document_id=document_id,
        source=source,
        content=content,
        chunking_config=ChunkingConfig(chunk_size=80, chunk_overlap=10),
    )

    assert isinstance(result, IngestionResult)
    assert result.document.document_id == document_id
    assert result.document.source == source
    assert [page.page_number for page in result.document.pages] == [1, 2]
    assert len(result.document.pages) == 2
    assert result.chunks


def test_ingest_pdf_chunks_preserve_returned_document_provenance() -> None:
    content = _text_pdf(("Alpha beta gamma delta.", "Second page text."))
    source = _source(size_bytes=len(content))

    result = ingest_pdf(
        document_id=uuid4(),
        source=source,
        content=content,
        chunking_config=ChunkingConfig(chunk_size=12, chunk_overlap=2),
    )

    assert [chunk.chunk_index for chunk in result.chunks] == list(
        range(len(result.chunks))
    )
    assert all(
        chunk.document_id == result.document.document_id for chunk in result.chunks
    )
    assert all(chunk.source == result.document.source for chunk in result.chunks)
    assert {chunk.page_number for chunk in result.chunks} == {1, 2}


def test_ingest_pdf_honors_custom_chunk_configuration() -> None:
    content = _text_pdf(("abcdefghijklmno",))

    result = ingest_pdf(
        document_id=uuid4(),
        source=_source(size_bytes=len(content)),
        content=content,
        chunking_config=ChunkingConfig(chunk_size=5, chunk_overlap=1),
    )

    assert [chunk.text for chunk in result.chunks] == [
        "abcde",
        "efghi",
        "ijklm",
        "mno",
    ]
    assert all(len(chunk.text) <= 5 for chunk in result.chunks)


def test_ingest_pdf_uses_normalized_text_for_chunks() -> None:
    content = _text_pdf(
        (
            "Alpha    beta gamma delta epsilon zeta eta theta iota kappa.",
            "Second    page keeps     spaces.",
        )
    )

    result = ingest_pdf(
        document_id=uuid4(),
        source=_source(size_bytes=len(content)),
        content=content,
        chunking_config=ChunkingConfig(chunk_size=25, chunk_overlap=5),
    )

    assert "  " not in result.document.pages[0].text
    assert all("  " not in chunk.text for chunk in result.chunks)
    assert len(result.chunks) > 2


def test_ingest_pdf_is_deterministic_for_identical_input() -> None:
    content = _text_pdf(("Alpha beta gamma delta epsilon.",))
    document_id = uuid4()
    source = _source(size_bytes=len(content))
    config = ChunkingConfig(chunk_size=10, chunk_overlap=2)

    first = ingest_pdf(
        document_id=document_id,
        source=source,
        content=content,
        chunking_config=config,
    )
    second = ingest_pdf(
        document_id=document_id,
        source=source,
        content=content,
        chunking_config=config,
    )

    assert first == second
    assert [chunk.chunk_id for chunk in first.chunks] == [
        chunk.chunk_id for chunk in second.chunks
    ]


def test_ingestion_result_is_immutable() -> None:
    content = _text_pdf(("Immutable result text.",))
    result = ingest_pdf(
        document_id=uuid4(),
        source=_source(size_bytes=len(content)),
        content=content,
    )

    with pytest.raises(FrozenInstanceError):
        result.chunks = ()


def test_ingest_pdf_does_not_mutate_source_object() -> None:
    content = _text_pdf(("Source metadata remains stable.",))
    source = _source(size_bytes=len(content))

    ingest_pdf(document_id=uuid4(), source=source, content=content)

    assert source.filename == "sample.pdf"
    assert source.media_type == "application/pdf"
    assert source.size_bytes == len(content)


def test_ingest_pdf_propagates_malformed_pdf_error() -> None:
    with pytest.raises(PdfParsingError):
        ingest_pdf(
            document_id=uuid4(),
            source=_source(size_bytes=len(b"not a pdf")),
            content=b"not a pdf",
        )


def test_ingest_pdf_propagates_encrypted_pdf_error() -> None:
    content = _encrypted_pdf()

    with pytest.raises(PdfParsingError):
        ingest_pdf(
            document_id=uuid4(),
            source=_source(size_bytes=len(content)),
            content=content,
        )


def test_ingest_pdf_propagates_blank_page_pdf_error() -> None:
    content = _blank_page_pdf()

    with pytest.raises(PdfParsingError):
        ingest_pdf(
            document_id=uuid4(),
            source=_source(size_bytes=len(content)),
            content=content,
        )


def test_invalid_chunk_configuration_raises_value_error() -> None:
    with pytest.raises(ValueError):
        ChunkingConfig(chunk_size=10, chunk_overlap=10)


def _source(*, size_bytes: int) -> DocumentSource:
    return DocumentSource(
        filename="sample.pdf",
        media_type="application/pdf",
        size_bytes=size_bytes,
    )


def _blank_page_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
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


def _text_pdf(page_texts: tuple[str, ...]) -> bytes:
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        _pages_object(len(page_texts)),
    ]

    font_object_number = 3 + len(page_texts)
    first_content_object_number = font_object_number + 1

    for index, _text in enumerate(page_texts, start=1):
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
