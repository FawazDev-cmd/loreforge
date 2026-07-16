from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from loreforge.documents import (
    ChunkingConfig,
    DocumentChunk,
    DocumentPage,
    DocumentSource,
    ParsedDocument,
    chunk_document,
)


def test_document_chunk_accepts_valid_provenance() -> None:
    document_id = uuid4()
    source = _source()
    chunk = DocumentChunk(
        chunk_id=uuid4(),
        document_id=document_id,
        source=source,
        page_number=1,
        chunk_index=0,
        text="Chunk text",
    )

    assert chunk.document_id == document_id
    assert chunk.source == source
    assert chunk.page_number == 1
    assert chunk.chunk_index == 0
    assert chunk.text == "Chunk text"


def test_document_chunk_rejects_invalid_page_number() -> None:
    with pytest.raises(ValueError, match="page_number"):
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source=_source(),
            page_number=0,
            chunk_index=0,
            text="Chunk text",
        )


def test_document_chunk_rejects_invalid_chunk_index() -> None:
    with pytest.raises(ValueError, match="chunk_index"):
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source=_source(),
            page_number=1,
            chunk_index=-1,
            text="Chunk text",
        )


def test_document_chunk_rejects_blank_text() -> None:
    with pytest.raises(ValueError, match="text"):
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source=_source(),
            page_number=1,
            chunk_index=0,
            text="   ",
        )


def test_chunking_config_accepts_defaults() -> None:
    config = ChunkingConfig()

    assert config.chunk_size == 1000
    assert config.chunk_overlap == 150


def test_chunking_config_rejects_non_positive_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        ChunkingConfig(chunk_size=0)


def test_chunking_config_rejects_negative_overlap() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        ChunkingConfig(chunk_size=10, chunk_overlap=-1)


def test_chunking_config_rejects_overlap_equal_to_chunk_size() -> None:
    with pytest.raises(ValueError, match="smaller"):
        ChunkingConfig(chunk_size=10, chunk_overlap=10)


def test_chunking_config_rejects_overlap_greater_than_chunk_size() -> None:
    with pytest.raises(ValueError, match="smaller"):
        ChunkingConfig(chunk_size=10, chunk_overlap=11)


def test_short_page_produces_one_chunk() -> None:
    document = _document((DocumentPage(page_number=1, text="Short page"),))

    chunks = chunk_document(document, ChunkingConfig(chunk_size=50, chunk_overlap=5))

    assert isinstance(chunks, tuple)
    assert [chunk.text for chunk in chunks] == ["Short page"]


def test_exact_size_page_produces_one_chunk() -> None:
    document = _document((DocumentPage(page_number=1, text="abcdefghij"),))

    chunks = chunk_document(document, ChunkingConfig(chunk_size=10, chunk_overlap=2))

    assert [chunk.text for chunk in chunks] == ["abcdefghij"]


def test_long_page_produces_multiple_chunks_with_size_limit() -> None:
    document = _document((DocumentPage(page_number=1, text="abcdefghijklmno"),))

    chunks = chunk_document(document, ChunkingConfig(chunk_size=5, chunk_overlap=0))

    assert [chunk.text for chunk in chunks] == ["abcde", "fghij", "klmno"]
    assert all(len(chunk.text) <= 5 for chunk in chunks)


def test_chunk_document_does_not_mutate_input_document() -> None:
    page = DocumentPage(page_number=1, text="Alpha beta gamma delta")
    document = _document((page,))

    chunk_document(document, ChunkingConfig(chunk_size=10, chunk_overlap=2))

    assert document.pages == (page,)
    assert document.pages[0].text == "Alpha beta gamma delta"


def test_chunks_preserve_document_provenance() -> None:
    document_id = uuid4()
    source = _source()
    document = ParsedDocument(
        document_id=document_id,
        source=source,
        pages=(
            DocumentPage(page_number=1, text="First page text"),
            DocumentPage(page_number=2, text="Second page text"),
        ),
    )

    chunks = chunk_document(document, ChunkingConfig(chunk_size=50, chunk_overlap=5))

    assert [chunk.document_id for chunk in chunks] == [document_id, document_id]
    assert [chunk.source for chunk in chunks] == [source, source]
    assert [chunk.page_number for chunk in chunks] == [1, 2]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]


def test_chunks_do_not_cross_page_boundaries() -> None:
    document = _document(
        (
            DocumentPage(page_number=1, text="Page one has unique apples."),
            DocumentPage(page_number=2, text="Page two has unique oranges."),
        )
    )

    chunks = chunk_document(document, ChunkingConfig(chunk_size=12, chunk_overlap=0))

    page_one_chunks = [chunk.text for chunk in chunks if chunk.page_number == 1]
    page_two_chunks = [chunk.text for chunk in chunks if chunk.page_number == 2]
    assert all("oranges" not in text for text in page_one_chunks)
    assert all("apples" not in text for text in page_two_chunks)


def test_page_order_is_preserved_in_chunks() -> None:
    document = _document(
        (
            DocumentPage(page_number=1, text="First page text"),
            DocumentPage(page_number=2, text="Second page text"),
        )
    )

    chunks = chunk_document(document, ChunkingConfig(chunk_size=8, chunk_overlap=0))

    assert [chunk.page_number for chunk in chunks] == sorted(
        chunk.page_number for chunk in chunks
    )


def test_overlap_is_preserved_within_one_page() -> None:
    document = _document((DocumentPage(page_number=1, text="abcdefghi"),))

    chunks = chunk_document(document, ChunkingConfig(chunk_size=5, chunk_overlap=2))

    assert [chunk.text for chunk in chunks] == ["abcde", "defgh", "ghi"]
    assert chunks[0].text[-2:] == chunks[1].text[:2]


def test_overlap_does_not_cross_page_boundaries() -> None:
    document = _document(
        (
            DocumentPage(page_number=1, text="abcdef"),
            DocumentPage(page_number=2, text="ghijkl"),
        )
    )

    chunks = chunk_document(document, ChunkingConfig(chunk_size=4, chunk_overlap=2))

    assert chunks[1].page_number == 1
    assert chunks[2].page_number == 2
    assert chunks[1].text == "cdef"
    assert chunks[2].text == "ghij"


def test_paragraph_boundary_is_preferred() -> None:
    document = _document(
        (DocumentPage(page_number=1, text="Alpha beta\n\nGamma delta epsilon"),)
    )

    chunks = chunk_document(document, ChunkingConfig(chunk_size=14, chunk_overlap=0))

    assert chunks[0].text == "Alpha beta"


def test_newline_boundary_is_preferred() -> None:
    document = _document(
        (DocumentPage(page_number=1, text="Alpha beta\nGamma delta epsilon"),)
    )

    chunks = chunk_document(document, ChunkingConfig(chunk_size=14, chunk_overlap=0))

    assert chunks[0].text == "Alpha beta"


def test_word_boundary_is_preferred_over_splitting_word() -> None:
    document = _document((DocumentPage(page_number=1, text="Alpha beta gamma"),))

    chunks = chunk_document(document, ChunkingConfig(chunk_size=12, chunk_overlap=0))

    assert chunks[0].text == "Alpha beta"


def test_hard_boundary_handles_long_text_without_whitespace() -> None:
    document = _document((DocumentPage(page_number=1, text="abcdefghijk"),))

    chunks = chunk_document(document, ChunkingConfig(chunk_size=5, chunk_overlap=0))

    assert [chunk.text for chunk in chunks] == ["abcde", "fghij", "k"]


def test_algorithm_always_advances_with_large_overlap() -> None:
    document = _document((DocumentPage(page_number=1, text="abcdefghij"),))

    chunks = chunk_document(document, ChunkingConfig(chunk_size=4, chunk_overlap=3))

    assert [chunk.text for chunk in chunks] == [
        "abcd",
        "bcde",
        "cdef",
        "defg",
        "efgh",
        "fghi",
        "ghij",
    ]


def test_repeated_chunking_is_deterministic() -> None:
    document = _document((DocumentPage(page_number=1, text="Alpha beta gamma"),))
    config = ChunkingConfig(chunk_size=8, chunk_overlap=2)

    assert chunk_document(document, config) == chunk_document(document, config)


def test_repeated_chunking_produces_identical_chunk_ids() -> None:
    document = _document((DocumentPage(page_number=1, text="Alpha beta gamma"),))
    config = ChunkingConfig(chunk_size=8, chunk_overlap=2)

    first = chunk_document(document, config)
    second = chunk_document(document, config)

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]


def test_changing_config_changes_chunk_identity_or_boundaries() -> None:
    document = _document((DocumentPage(page_number=1, text="Alpha beta gamma"),))

    small_chunks = chunk_document(
        document, ChunkingConfig(chunk_size=8, chunk_overlap=2)
    )
    large_chunks = chunk_document(
        document, ChunkingConfig(chunk_size=20, chunk_overlap=2)
    )

    assert small_chunks != large_chunks
    assert [chunk.chunk_id for chunk in small_chunks] != [
        chunk.chunk_id for chunk in large_chunks
    ]


def test_different_page_provenance_produces_distinct_chunk_ids() -> None:
    document = _document(
        (
            DocumentPage(page_number=1, text="Same text"),
            DocumentPage(page_number=2, text="Same text"),
        )
    )

    chunks = chunk_document(document, ChunkingConfig(chunk_size=50, chunk_overlap=5))

    assert chunks[0].text == chunks[1].text
    assert chunks[0].chunk_id != chunks[1].chunk_id


def test_document_chunk_is_immutable() -> None:
    chunk = chunk_document(
        _document((DocumentPage(page_number=1, text="Immutable chunk"),))
    )[0]

    with pytest.raises(FrozenInstanceError):
        chunk.text = "Changed"


def test_chunking_config_is_immutable() -> None:
    config = ChunkingConfig()

    with pytest.raises(FrozenInstanceError):
        config.chunk_size = 2000


def _document(pages: tuple[DocumentPage, ...]) -> ParsedDocument:
    return ParsedDocument(document_id=uuid4(), source=_source(), pages=pages)


def _source() -> DocumentSource:
    return DocumentSource(
        filename="sample.pdf",
        media_type="application/pdf",
        size_bytes=1024,
    )
