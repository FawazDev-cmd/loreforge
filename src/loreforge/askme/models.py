"""Safe application-level AskMe result contracts."""

from dataclasses import dataclass
from re import fullmatch
from uuid import UUID

_CITATION_ID_PATTERN = r"S[1-9][0-9]*"


@dataclass(frozen=True, slots=True)
class AskMeRequest:
    """End-user question submitted to AskMe."""

    question: str

    def __post_init__(self) -> None:
        _validate_nonblank_string(self.question, "question")


@dataclass(frozen=True, slots=True)
class AskMeCitation:
    """Validated source citation safe to return to end users."""

    citation_id: str
    document_id: UUID
    filename: str
    page_number: int
    chunk_id: UUID

    def __post_init__(self) -> None:
        _validate_citation_id(self.citation_id)
        if type(self.document_id) is not UUID:
            msg = "document_id must be a UUID"
            raise ValueError(msg)
        _validate_nonblank_string(self.filename, "filename")
        _validate_positive_int(self.page_number, "page_number")
        if type(self.chunk_id) is not UUID:
            msg = "chunk_id must be a UUID"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class AskMeResult:
    """Safe AskMe answer returned by the application service."""

    request_id: UUID
    question: str
    answer: str
    citations: tuple[AskMeCitation, ...]

    def __post_init__(self) -> None:
        if type(self.request_id) is not UUID:
            msg = "request_id must be a UUID"
            raise ValueError(msg)
        _validate_nonblank_string(self.question, "question")
        _validate_nonblank_string(self.answer, "answer")
        if type(self.citations) is not tuple:
            msg = "citations must be a tuple"
            raise ValueError(msg)
        if not self.citations:
            msg = "citations must contain at least one citation"
            raise ValueError(msg)
        citation_ids = tuple(citation.citation_id for citation in self.citations)
        if len(set(citation_ids)) != len(citation_ids):
            msg = "citation IDs must be unique"
            raise ValueError(msg)


def _validate_nonblank_string(value: str, name: str) -> None:
    value_object: object = value
    if type(value_object) is not str:
        msg = f"{name} must be a string"
        raise ValueError(msg)
    if not value.strip():
        msg = f"{name} must not be empty"
        raise ValueError(msg)


def _validate_citation_id(citation_id: str) -> None:
    _validate_nonblank_string(citation_id, "citation_id")
    if fullmatch(_CITATION_ID_PATTERN, citation_id) is None:
        msg = "citation_id must match S followed by a positive integer"
        raise ValueError(msg)


def _validate_positive_int(value: int, name: str) -> None:
    value_object: object = value
    if type(value_object) is not int:
        msg = f"{name} must be an integer"
        raise ValueError(msg)
    if value <= 0:
        msg = f"{name} must be greater than zero"
        raise ValueError(msg)
