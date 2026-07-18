from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from loreforge.indexing import IndexedDocumentResult

DOC = UUID("00000000-0000-0000-0000-000000000001")


def test_indexed_document_result_accepts_complete_counts() -> None:
    result = IndexedDocumentResult(
        document_id=DOC,
        chunk_count=2,
        semantic_indexed_count=2,
        lexical_indexed_count=2,
    )

    assert result.document_id == DOC
    assert result.chunk_count == 2
    assert result.semantic_indexed_count == 2
    assert result.lexical_indexed_count == 2


def test_indexed_document_result_is_immutable() -> None:
    result = IndexedDocumentResult(
        document_id=DOC,
        chunk_count=1,
        semantic_indexed_count=1,
        lexical_indexed_count=1,
    )

    with pytest.raises(FrozenInstanceError):
        result.chunk_count = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("chunk_count", "semantic_count", "lexical_count"),
    [
        (0, 0, 0),
        (-1, 0, 0),
        (2, 1, 2),
        (2, 2, 1),
    ],
)
def test_indexed_document_result_rejects_invalid_counts(
    chunk_count: int,
    semantic_count: int,
    lexical_count: int,
) -> None:
    with pytest.raises(ValueError):
        IndexedDocumentResult(
            document_id=DOC,
            chunk_count=chunk_count,
            semantic_indexed_count=semantic_count,
            lexical_indexed_count=lexical_count,
        )


def test_indexed_document_result_requires_uuid_document_id() -> None:
    with pytest.raises(ValueError, match="document_id"):
        IndexedDocumentResult(  # type: ignore[arg-type]
            document_id="not-a-uuid",
            chunk_count=1,
            semantic_indexed_count=1,
            lexical_indexed_count=1,
        )
