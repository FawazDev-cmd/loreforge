"""Document indexing result contracts."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class IndexedDocumentResult:
    """Counts for one successfully indexed document."""

    document_id: UUID
    chunk_count: int
    semantic_indexed_count: int
    lexical_indexed_count: int

    def __post_init__(self) -> None:
        if type(self.document_id) is not UUID:
            msg = "document_id must be a UUID"
            raise ValueError(msg)
        _validate_nonnegative_int(self.chunk_count, "chunk_count")
        _validate_nonnegative_int(
            self.semantic_indexed_count,
            "semantic_indexed_count",
        )
        _validate_nonnegative_int(
            self.lexical_indexed_count,
            "lexical_indexed_count",
        )
        if self.chunk_count == 0:
            msg = "chunk_count must be greater than zero"
            raise ValueError(msg)
        if self.semantic_indexed_count != self.chunk_count:
            msg = "semantic_indexed_count must equal chunk_count"
            raise ValueError(msg)
        if self.lexical_indexed_count != self.chunk_count:
            msg = "lexical_indexed_count must equal chunk_count"
            raise ValueError(msg)


def _validate_nonnegative_int(value: int, name: str) -> None:
    value_object: object = value
    if type(value_object) is not int:
        msg = f"{name} must be an integer"
        raise ValueError(msg)
    if value < 0:
        msg = f"{name} must be greater than or equal to zero"
        raise ValueError(msg)
