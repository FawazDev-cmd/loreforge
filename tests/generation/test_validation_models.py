from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from loreforge.generation import (
    CitationExtraction,
    CitationValidationResult,
    EvidenceContext,
    EvidenceItem,
    GroundedAnswer,
    SourceReference,
    ValidatedGroundedAnswer,
)

CHUNK_ID_1 = UUID("00000000-0000-0000-0000-000000000101")
CHUNK_ID_2 = UUID("00000000-0000-0000-0000-000000000102")
DOCUMENT_ID_1 = UUID("00000000-0000-0000-0000-000000000201")
DOCUMENT_ID_2 = UUID("00000000-0000-0000-0000-000000000202")


def test_citation_extraction_accepts_empty_values() -> None:
    extraction = CitationExtraction(occurrences=(), citation_ids=())

    assert extraction.occurrences == ()
    assert extraction.citation_ids == ()


def test_citation_extraction_accepts_one_citation() -> None:
    extraction = CitationExtraction(occurrences=("S1",), citation_ids=("S1",))

    assert extraction.citation_ids == ("S1",)


def test_citation_extraction_accepts_repeated_occurrences() -> None:
    extraction = CitationExtraction(
        occurrences=("S2", "S1", "S2"), citation_ids=("S2", "S1")
    )

    assert extraction.occurrences == ("S2", "S1", "S2")


def test_citation_extraction_preserves_first_occurrence_unique_order() -> None:
    extraction = CitationExtraction(
        occurrences=("S3", "S2", "S3", "S1"), citation_ids=("S3", "S2", "S1")
    )

    assert extraction.citation_ids == ("S3", "S2", "S1")


@pytest.mark.parametrize("citation_id", ["", "S0", "s1", "S 1", "S-1", "1"])
def test_citation_extraction_rejects_invalid_citation_format(citation_id: str) -> None:
    with pytest.raises(ValueError, match="citation"):
        CitationExtraction(occurrences=(citation_id,), citation_ids=(citation_id,))


def test_citation_extraction_rejects_duplicate_citation_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        CitationExtraction(occurrences=("S1", "S1"), citation_ids=("S1", "S1"))


def test_citation_extraction_rejects_ids_inconsistent_with_occurrences() -> None:
    with pytest.raises(ValueError, match="first-occurrence"):
        CitationExtraction(occurrences=("S2", "S1"), citation_ids=("S1", "S2"))


def test_citation_extraction_is_immutable() -> None:
    extraction = CitationExtraction(occurrences=("S1",), citation_ids=("S1",))

    with pytest.raises(FrozenInstanceError):
        extraction.citation_ids = ()


def test_validation_result_accepts_supported_only_result() -> None:
    result = CitationValidationResult(
        citation_ids=("S1", "S2"),
        supported_citation_ids=("S1", "S2"),
        unsupported_citation_ids=(),
        missing_citations=False,
        is_valid=True,
    )

    assert result.is_valid is True


def test_validation_result_accepts_unsupported_result() -> None:
    result = CitationValidationResult(
        citation_ids=("S1", "S99"),
        supported_citation_ids=("S1",),
        unsupported_citation_ids=("S99",),
        missing_citations=False,
        is_valid=False,
    )

    assert result.unsupported_citation_ids == ("S99",)


def test_validation_result_accepts_missing_citation_result() -> None:
    result = CitationValidationResult(
        citation_ids=(),
        supported_citation_ids=(),
        unsupported_citation_ids=(),
        missing_citations=True,
        is_valid=False,
    )

    assert result.missing_citations is True


@pytest.mark.parametrize("citation_id", ["S0", "s1", "S 1", "S-1"])
def test_validation_result_rejects_invalid_citation_values(citation_id: str) -> None:
    with pytest.raises(ValueError, match="citation"):
        CitationValidationResult(
            citation_ids=(citation_id,),
            supported_citation_ids=(citation_id,),
            unsupported_citation_ids=(),
            missing_citations=False,
            is_valid=True,
        )


def test_validation_result_rejects_duplicate_values() -> None:
    with pytest.raises(ValueError, match="unique"):
        CitationValidationResult(
            citation_ids=("S1", "S1"),
            supported_citation_ids=("S1",),
            unsupported_citation_ids=(),
            missing_citations=False,
            is_valid=True,
        )


def test_validation_result_rejects_supported_unsupported_overlap() -> None:
    with pytest.raises(ValueError, match="overlap"):
        CitationValidationResult(
            citation_ids=("S1",),
            supported_citation_ids=("S1",),
            unsupported_citation_ids=("S1",),
            missing_citations=False,
            is_valid=True,
        )


def test_validation_result_rejects_incomplete_accounting() -> None:
    with pytest.raises(ValueError, match="account"):
        CitationValidationResult(
            citation_ids=("S1", "S2"),
            supported_citation_ids=("S1",),
            unsupported_citation_ids=(),
            missing_citations=False,
            is_valid=True,
        )


def test_validation_result_rejects_incorrect_ordering() -> None:
    with pytest.raises(ValueError, match="order"):
        CitationValidationResult(
            citation_ids=("S1", "S2"),
            supported_citation_ids=("S2", "S1"),
            unsupported_citation_ids=(),
            missing_citations=False,
            is_valid=True,
        )


def test_validation_result_rejects_incorrect_missing_state() -> None:
    with pytest.raises(ValueError, match="missing"):
        CitationValidationResult(
            citation_ids=("S1",),
            supported_citation_ids=("S1",),
            unsupported_citation_ids=(),
            missing_citations=True,
            is_valid=True,
        )


def test_validation_result_rejects_incorrect_validity_state() -> None:
    with pytest.raises(ValueError, match="is_valid"):
        CitationValidationResult(
            citation_ids=("S1", "S99"),
            supported_citation_ids=("S1",),
            unsupported_citation_ids=("S99",),
            missing_citations=False,
            is_valid=True,
        )


def test_validation_result_rejects_non_boolean_states() -> None:
    with pytest.raises(ValueError, match="missing_citations"):
        CitationValidationResult(
            citation_ids=(),
            supported_citation_ids=(),
            unsupported_citation_ids=(),
            missing_citations=1,  # type: ignore[arg-type]
            is_valid=False,
        )

    with pytest.raises(ValueError, match="is_valid"):
        CitationValidationResult(
            citation_ids=(),
            supported_citation_ids=(),
            unsupported_citation_ids=(),
            missing_citations=True,
            is_valid=0,  # type: ignore[arg-type]
        )


def test_validation_result_is_immutable() -> None:
    result = CitationValidationResult(
        citation_ids=("S1",),
        supported_citation_ids=("S1",),
        unsupported_citation_ids=(),
        missing_citations=False,
        is_valid=True,
    )

    with pytest.raises(FrozenInstanceError):
        result.is_valid = False


def test_validated_grounded_answer_accepts_valid_construction() -> None:
    answer = _grounded_answer(citations_validated=True)
    validation = _valid_validation(("S1",))

    validated = ValidatedGroundedAnswer(
        grounded_answer=answer,
        citation_validation=validation,
        cited_sources=(answer.sources[0],),
    )

    assert validated.grounded_answer == answer


def test_validated_grounded_answer_rejects_unvalidated_answer() -> None:
    with pytest.raises(ValueError, match="citations_validated"):
        ValidatedGroundedAnswer(
            grounded_answer=_grounded_answer(citations_validated=False),
            citation_validation=_valid_validation(("S1",)),
            cited_sources=(_source_reference(),),
        )


def test_validated_grounded_answer_rejects_invalid_validation_result() -> None:
    validation = CitationValidationResult(
        citation_ids=(),
        supported_citation_ids=(),
        unsupported_citation_ids=(),
        missing_citations=True,
        is_valid=False,
    )

    with pytest.raises(ValueError, match="valid"):
        ValidatedGroundedAnswer(
            grounded_answer=_grounded_answer(citations_validated=True),
            citation_validation=validation,
            cited_sources=(_source_reference(),),
        )


def test_validated_grounded_answer_rejects_empty_cited_sources() -> None:
    with pytest.raises(ValueError, match="cited_sources"):
        ValidatedGroundedAnswer(
            grounded_answer=_grounded_answer(citations_validated=True),
            citation_validation=_valid_validation(("S1",)),
            cited_sources=(),
        )


def test_validated_grounded_answer_rejects_duplicate_cited_source_ids() -> None:
    answer = _grounded_answer(citations_validated=True, two_sources=True)
    with pytest.raises(ValueError, match="unique"):
        ValidatedGroundedAnswer(
            grounded_answer=answer,
            citation_validation=_valid_validation(("S1", "S1")),
            cited_sources=(answer.sources[0], answer.sources[0]),
        )


def test_validated_grounded_answer_rejects_cited_source_order_mismatch() -> None:
    answer = _grounded_answer(citations_validated=True, two_sources=True)
    validation = _valid_validation(("S2", "S1"))

    with pytest.raises(ValueError, match="order"):
        ValidatedGroundedAnswer(
            grounded_answer=answer,
            citation_validation=validation,
            cited_sources=(answer.sources[0], answer.sources[1]),
        )


def test_validated_grounded_answer_rejects_absent_source() -> None:
    answer = _grounded_answer(citations_validated=True)
    absent = _source_reference(citation_id="S2", chunk_id=CHUNK_ID_2)

    with pytest.raises(ValueError, match="exist"):
        ValidatedGroundedAnswer(
            grounded_answer=answer,
            citation_validation=_valid_validation(("S2",)),
            cited_sources=(absent,),
        )


def test_validated_grounded_answer_rejects_source_value_mismatch() -> None:
    answer = _grounded_answer(citations_validated=True)
    mismatched = _source_reference(filename="other.pdf")

    with pytest.raises(ValueError, match="match"):
        ValidatedGroundedAnswer(
            grounded_answer=answer,
            citation_validation=_valid_validation(("S1",)),
            cited_sources=(mismatched,),
        )


def test_validated_grounded_answer_is_immutable() -> None:
    answer = _grounded_answer(citations_validated=True)
    validated = ValidatedGroundedAnswer(
        grounded_answer=answer,
        citation_validation=_valid_validation(("S1",)),
        cited_sources=(answer.sources[0],),
    )

    with pytest.raises(FrozenInstanceError):
        validated.cited_sources = ()


def _valid_validation(citation_ids: tuple[str, ...]) -> CitationValidationResult:
    return CitationValidationResult(
        citation_ids=citation_ids,
        supported_citation_ids=citation_ids,
        unsupported_citation_ids=(),
        missing_citations=False,
        is_valid=True,
    )


def _source_reference(
    *,
    citation_id: str = "S1",
    document_id: UUID = DOCUMENT_ID_1,
    chunk_id: UUID = CHUNK_ID_1,
    filename: str = "sample.pdf",
    page_number: int = 1,
) -> SourceReference:
    return SourceReference(
        citation_id=citation_id,
        document_id=document_id,
        chunk_id=chunk_id,
        filename=filename,
        page_number=page_number,
    )


def _grounded_answer(
    *, citations_validated: bool, two_sources: bool = False
) -> GroundedAnswer:
    first = _source_reference()
    sources = (first,)
    items = (_evidence_item(),)
    if two_sources:
        second = _source_reference(
            citation_id="S2", document_id=DOCUMENT_ID_2, chunk_id=CHUNK_ID_2
        )
        sources = (first, second)
        items = (
            items[0],
            _evidence_item(
                citation_id="S2", document_id=DOCUMENT_ID_2, chunk_id=CHUNK_ID_2
            ),
        )
    rendered_text = "\n\n".join(
        (
            f"[{item.citation_id}]\n"
            f"Source: {item.filename}\n"
            f"Page: {item.page_number}\n"
            "Content:\n"
            f"{item.text}"
        )
        for item in items
    )
    evidence = EvidenceContext(
        items=items,
        rendered_text=rendered_text,
        total_characters=len(rendered_text),
        truncated=False,
    )
    return GroundedAnswer(
        question="question",
        answer_text="answer [S1]",
        sources=sources,
        evidence=evidence,
        provider_model="model",
        finish_reason="stop",
        citations_validated=citations_validated,
    )


def _evidence_item(
    *,
    citation_id: str = "S1",
    document_id: UUID = DOCUMENT_ID_1,
    chunk_id: UUID = CHUNK_ID_1,
    filename: str = "sample.pdf",
    page_number: int = 1,
    text: str = "Evidence text",
) -> EvidenceItem:
    return EvidenceItem(
        citation_id=citation_id,
        chunk_id=chunk_id,
        document_id=document_id,
        filename=filename,
        page_number=page_number,
        text=text,
        reranker_score=1.0,
        retrieval_rank=1,
    )
