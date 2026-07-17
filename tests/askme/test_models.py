from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from loreforge.askme import AskMeCitation, AskMeRequest, AskMeResult

REQUEST_ID = UUID("00000000-0000-0000-0000-000000000001")
DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000201")
CHUNK_ID = UUID("00000000-0000-0000-0000-000000000101")
CHUNK_ID_2 = UUID("00000000-0000-0000-0000-000000000102")


class StringSubclass(str):
    pass


def test_request_valid_question() -> None:
    request = AskMeRequest("What is the refund policy?")

    assert request.question == "What is the refund policy?"


def test_request_preserves_surrounding_whitespace() -> None:
    request = AskMeRequest("  What is the refund policy?  ")

    assert request.question == "  What is the refund policy?  "


@pytest.mark.parametrize("question", ["", "   "])
def test_request_blank_question_rejected(question: str) -> None:
    with pytest.raises(ValueError, match="question"):
        AskMeRequest(question)


@pytest.mark.parametrize("question", [1, StringSubclass("question")])
def test_request_non_exact_string_rejected(question: object) -> None:
    with pytest.raises(ValueError, match="question"):
        AskMeRequest(question)  # type: ignore[arg-type]


def test_request_is_immutable() -> None:
    request = AskMeRequest("question")

    with pytest.raises(FrozenInstanceError):
        request.question = "changed"


def test_citation_valid_values() -> None:
    citation = _citation()

    assert citation.citation_id == "S1"
    assert citation.document_id == DOCUMENT_ID
    assert citation.filename == "refund-policy.pdf"
    assert citation.page_number == 2
    assert citation.chunk_id == CHUNK_ID


@pytest.mark.parametrize("citation_id", ["", "S0", "s1", "S 1", "S-1", "1"])
def test_citation_malformed_id_rejected(citation_id: str) -> None:
    with pytest.raises(ValueError, match="citation_id"):
        _citation(citation_id=citation_id)


def test_citation_zero_number_rejected() -> None:
    with pytest.raises(ValueError, match="citation_id"):
        _citation(citation_id="S0")


@pytest.mark.parametrize("filename", ["", "   "])
def test_citation_blank_filename_rejected(filename: str) -> None:
    with pytest.raises(ValueError, match="filename"):
        _citation(filename=filename)


@pytest.mark.parametrize("page_number", [0, -1])
def test_citation_non_positive_page_rejected(page_number: int) -> None:
    with pytest.raises(ValueError, match="page_number"):
        _citation(page_number=page_number)


def test_citation_boolean_page_rejected() -> None:
    with pytest.raises(ValueError, match="page_number"):
        _citation(page_number=True)  # type: ignore[arg-type]


def test_citation_is_immutable() -> None:
    citation = _citation()

    with pytest.raises(FrozenInstanceError):
        citation.filename = "changed.pdf"


def test_result_valid_values() -> None:
    result = _result()

    assert result.request_id == REQUEST_ID
    assert result.question == "What is the refund policy?"
    assert result.answer == "Refunds are available within 14 days [S1]."


def test_result_preserves_citation_order() -> None:
    citations = (_citation(citation_id="S2", chunk_id=CHUNK_ID_2), _citation())

    result = _result(citations=citations)

    assert result.citations == citations


@pytest.mark.parametrize("question", ["", "   "])
def test_result_blank_question_rejected(question: str) -> None:
    with pytest.raises(ValueError, match="question"):
        _result(question=question)


@pytest.mark.parametrize("answer", ["", "   "])
def test_result_blank_answer_rejected(answer: str) -> None:
    with pytest.raises(ValueError, match="answer"):
        _result(answer=answer)


def test_result_empty_citations_rejected() -> None:
    with pytest.raises(ValueError, match="citations"):
        _result(citations=())


def test_result_duplicate_citation_ids_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        _result(citations=(_citation(), _citation(chunk_id=CHUNK_ID_2)))


def test_result_is_immutable() -> None:
    result = _result()

    with pytest.raises(FrozenInstanceError):
        result.answer = "changed"


def _citation(
    *,
    citation_id: str = "S1",
    document_id: UUID = DOCUMENT_ID,
    filename: str = "refund-policy.pdf",
    page_number: int = 2,
    chunk_id: UUID = CHUNK_ID,
) -> AskMeCitation:
    return AskMeCitation(
        citation_id=citation_id,
        document_id=document_id,
        filename=filename,
        page_number=page_number,
        chunk_id=chunk_id,
    )


def _result(
    *,
    request_id: UUID = REQUEST_ID,
    question: str = "What is the refund policy?",
    answer: str = "Refunds are available within 14 days [S1].",
    citations: tuple[AskMeCitation, ...] = (_citation(),),
) -> AskMeResult:
    return AskMeResult(
        request_id=request_id,
        question=question,
        answer=answer,
        citations=citations,
    )
