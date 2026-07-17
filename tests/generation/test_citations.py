from uuid import UUID

import pytest

from loreforge.generation import (
    CitationEnforcementError,
    CitationExtraction,
    EvidenceContext,
    EvidenceItem,
    GroundedAnswer,
    SourceReference,
    extract_citations,
    validate_citations,
    validate_grounded_answer,
)

CHUNK_ID_1 = UUID("00000000-0000-0000-0000-000000000101")
CHUNK_ID_2 = UUID("00000000-0000-0000-0000-000000000102")
CHUNK_ID_3 = UUID("00000000-0000-0000-0000-000000000103")
DOCUMENT_ID_1 = UUID("00000000-0000-0000-0000-000000000201")
DOCUMENT_ID_2 = UUID("00000000-0000-0000-0000-000000000202")
DOCUMENT_ID_3 = UUID("00000000-0000-0000-0000-000000000203")


def test_extract_citations_finds_one_citation() -> None:
    extraction = extract_citations("Policy applies [S1].")

    assert extraction.occurrences == ("S1",)
    assert extraction.citation_ids == ("S1",)


def test_extract_citations_finds_multiple_citations() -> None:
    extraction = extract_citations("Policy [S2]. Approval [S1].")

    assert extraction.occurrences == ("S2", "S1")
    assert extraction.citation_ids == ("S2", "S1")


def test_extract_citations_preserves_repeated_occurrences() -> None:
    extraction = extract_citations("Policy [S2]. Approval [S1]. Again [S2].")

    assert extraction.occurrences == ("S2", "S1", "S2")
    assert extraction.citation_ids == ("S2", "S1")


def test_extract_citations_preserves_first_occurrence_ordering() -> None:
    extraction = extract_citations("A [S3]. B [S2]. C [S3]. D [S1].")

    assert extraction.citation_ids == ("S3", "S2", "S1")


def test_extract_citations_handles_punctuation() -> None:
    extraction = extract_citations("Policy applies [S1], and approval follows [S2].")

    assert extraction.citation_ids == ("S1", "S2")


def test_extract_citations_handles_marker_at_beginning() -> None:
    assert extract_citations("[S1] Policy applies.").citation_ids == ("S1",)


def test_extract_citations_handles_marker_at_end() -> None:
    assert extract_citations("Policy applies. [S1]").citation_ids == ("S1",)


def test_extract_citations_handles_multiline_answer() -> None:
    extraction = extract_citations("Line one [S1].\nLine two [S2].")

    assert extraction.citation_ids == ("S1", "S2")


def test_extract_citations_returns_empty_for_no_citations() -> None:
    assert extract_citations("Policy applies.") == CitationExtraction((), ())


@pytest.mark.parametrize(
    "answer_text",
    ["lowercase [s1].", "zero [S0].", "space [S 1].", "negative [S-1].", "bad [S1"],
)
def test_extract_citations_ignores_invalid_markers(answer_text: str) -> None:
    assert extract_citations(answer_text).citation_ids == ()


def test_extract_citations_ignores_double_bracket_form() -> None:
    assert extract_citations("Double [[S1]] marker.").citation_ids == ()


@pytest.mark.parametrize("answer_text", ["", "   "])
def test_extract_citations_rejects_blank_answer(answer_text: str) -> None:
    with pytest.raises(ValueError, match="answer_text"):
        extract_citations(answer_text)


def test_extract_citations_is_deterministic() -> None:
    text = "Policy [S2]. Approval [S1]. Again [S2]."

    assert extract_citations(text) == extract_citations(text)


def test_extract_citations_does_not_mutate_input_string() -> None:
    text = "Policy [S1]."
    before = text

    extract_citations(text)

    assert text == before


def test_validate_citations_all_supported() -> None:
    result = validate_citations(
        extraction=CitationExtraction(("S1", "S2"), ("S1", "S2")),
        sources=(_source("S1"), _source("S2", CHUNK_ID_2, DOCUMENT_ID_2)),
    )

    assert result.supported_citation_ids == ("S1", "S2")
    assert result.is_valid is True


def test_validate_citations_accepts_subset_of_sources() -> None:
    result = validate_citations(
        extraction=CitationExtraction(("S2",), ("S2",)),
        sources=(
            _source("S1"),
            _source("S2", CHUNK_ID_2, DOCUMENT_ID_2),
            _source("S3", CHUNK_ID_3, DOCUMENT_ID_3),
        ),
    )

    assert result.supported_citation_ids == ("S2",)
    assert result.is_valid is True


def test_validate_citations_detects_unsupported_citation() -> None:
    result = validate_citations(
        extraction=CitationExtraction(("S99",), ("S99",)),
        sources=(_source("S1"),),
    )

    assert result.unsupported_citation_ids == ("S99",)
    assert result.is_valid is False


def test_validate_citations_detects_mixed_supported_and_unsupported() -> None:
    result = validate_citations(
        extraction=CitationExtraction(("S1", "S99"), ("S1", "S99")),
        sources=(_source("S1"),),
    )

    assert result.supported_citation_ids == ("S1",)
    assert result.unsupported_citation_ids == ("S99",)


def test_validate_citations_reports_missing_state() -> None:
    result = validate_citations(
        extraction=CitationExtraction((), ()),
        sources=(_source("S1"),),
    )

    assert result.missing_citations is True
    assert result.is_valid is False


def test_validate_citations_orders_supported_and_unsupported_by_extraction() -> None:
    result = validate_citations(
        extraction=CitationExtraction(
            ("S99", "S2", "S98", "S1"), ("S99", "S2", "S98", "S1")
        ),
        sources=(_source("S1"), _source("S2", CHUNK_ID_2, DOCUMENT_ID_2)),
    )

    assert result.supported_citation_ids == ("S2", "S1")
    assert result.unsupported_citation_ids == ("S99", "S98")


def test_validate_citations_repeated_occurrences_do_not_duplicate_ids() -> None:
    result = validate_citations(
        extraction=CitationExtraction(("S1", "S1"), ("S1",)),
        sources=(_source("S1"),),
    )

    assert result.citation_ids == ("S1",)


def test_validate_citations_rejects_empty_sources() -> None:
    with pytest.raises(ValueError, match="sources"):
        validate_citations(extraction=CitationExtraction(("S1",), ("S1",)), sources=())


def test_validate_citations_rejects_duplicate_source_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        validate_citations(
            extraction=CitationExtraction(("S1",), ("S1",)),
            sources=(_source("S1"), _source("S1", CHUNK_ID_2, DOCUMENT_ID_2)),
        )


def test_validate_citations_does_not_mutate_inputs() -> None:
    extraction = CitationExtraction(("S1",), ("S1",))
    sources = (_source("S1"),)
    before = (extraction, sources)

    validate_citations(extraction=extraction, sources=sources)

    assert (extraction, sources) == before


def test_validate_grounded_answer_accepts_single_citation() -> None:
    answer = _grounded_answer(answer_text="Employees receive leave [S1].")

    validated = validate_grounded_answer(answer)

    assert validated.grounded_answer.citations_validated is True
    assert validated.cited_sources == (answer.sources[0],)


def test_validate_grounded_answer_accepts_multiple_citations() -> None:
    answer = _grounded_answer(answer_text="A [S1]. B [S2].", source_count=2)

    validated = validate_grounded_answer(answer)

    assert [source.citation_id for source in validated.cited_sources] == ["S1", "S2"]


def test_validate_grounded_answer_repeated_citation_produces_one_source() -> None:
    answer = _grounded_answer(answer_text="A [S1]. B [S1].")

    validated = validate_grounded_answer(answer)

    assert validated.cited_sources == (answer.sources[0],)


def test_validate_grounded_answer_source_order_follows_first_occurrence() -> None:
    answer = _grounded_answer(answer_text="B [S2]. A [S1].", source_count=2)

    validated = validate_grounded_answer(answer)

    assert [source.citation_id for source in validated.cited_sources] == ["S2", "S1"]


def test_validate_grounded_answer_accepts_subset_of_sources() -> None:
    answer = _grounded_answer(answer_text="Only second source [S2].", source_count=3)

    validated = validate_grounded_answer(answer)

    assert [source.citation_id for source in validated.cited_sources] == ["S2"]


def test_validate_grounded_answer_preserves_answer_text_exactly() -> None:
    text = "  Exact generated answer [S1].\n"
    answer = _grounded_answer(answer_text=text)

    validated = validate_grounded_answer(answer)

    assert validated.grounded_answer.answer_text == text


def test_validate_grounded_answer_preserves_evidence_exactly() -> None:
    answer = _grounded_answer(answer_text="Answer [S1].")

    validated = validate_grounded_answer(answer)

    assert validated.grounded_answer.evidence is answer.evidence


def test_validate_grounded_answer_preserves_provider_metadata() -> None:
    answer = _grounded_answer(
        answer_text="Answer [S1].", provider_model="model-x", finish_reason="length"
    )

    validated = validate_grounded_answer(answer)

    assert validated.grounded_answer.provider_model == "model-x"
    assert validated.grounded_answer.finish_reason == "length"


def test_validate_grounded_answer_original_answer_remains_unvalidated() -> None:
    answer = _grounded_answer(answer_text="Answer [S1].")

    validate_grounded_answer(answer)

    assert answer.citations_validated is False


def test_validate_grounded_answer_rejects_no_citation_answer() -> None:
    with pytest.raises(CitationEnforcementError, match="no supported citation"):
        validate_grounded_answer(_grounded_answer(answer_text="No citation here."))


def test_validate_grounded_answer_rejects_unsupported_citation() -> None:
    with pytest.raises(CitationEnforcementError, match="unsupported"):
        validate_grounded_answer(_grounded_answer(answer_text="Unsupported [S99]."))


def test_validate_grounded_answer_rejects_mixed_supported_and_unsupported() -> None:
    with pytest.raises(CitationEnforcementError, match="unsupported"):
        validate_grounded_answer(_grounded_answer(answer_text="Mixed [S1] and [S99]."))


def test_validate_grounded_answer_error_omits_full_answer_text() -> None:
    text = "This full answer text should not appear in the error."

    with pytest.raises(CitationEnforcementError) as error:
        validate_grounded_answer(_grounded_answer(answer_text=text))

    assert text not in str(error.value)


def test_validate_grounded_answer_is_deterministic() -> None:
    answer = _grounded_answer(answer_text="Answer [S1].")

    assert validate_grounded_answer(answer) == validate_grounded_answer(answer)


def test_validate_grounded_answer_does_not_check_claim_semantics() -> None:
    answer = _grounded_answer(answer_text="The moon is made of cheese [S1].")

    validated = validate_grounded_answer(answer)

    assert validated.grounded_answer.answer_text == "The moon is made of cheese [S1]."


def test_validate_grounded_answer_calls_extraction_and_validation_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import loreforge.generation.citations as citations

    calls = {"extract": 0, "validate": 0}
    original_extract = citations.extract_citations
    original_validate = citations.validate_citations

    def spy_extract(answer_text: str) -> CitationExtraction:
        calls["extract"] += 1
        return original_extract(answer_text)

    def spy_validate(
        *, extraction: CitationExtraction, sources: tuple[SourceReference, ...]
    ):
        calls["validate"] += 1
        return original_validate(extraction=extraction, sources=sources)

    monkeypatch.setattr(citations, "extract_citations", spy_extract)
    monkeypatch.setattr(citations, "validate_citations", spy_validate)

    validate_grounded_answer(_grounded_answer(answer_text="Answer [S1]."))

    assert calls == {"extract": 1, "validate": 1}


def _source(
    citation_id: str,
    chunk_id: UUID = CHUNK_ID_1,
    document_id: UUID = DOCUMENT_ID_1,
) -> SourceReference:
    return SourceReference(
        citation_id=citation_id,
        document_id=document_id,
        chunk_id=chunk_id,
        filename=f"{citation_id}.pdf",
        page_number=int(citation_id[1:]),
    )


def _grounded_answer(
    *,
    answer_text: str,
    source_count: int = 1,
    provider_model: str = "model",
    finish_reason: str | None = "stop",
) -> GroundedAnswer:
    source_specs = (
        ("S1", CHUNK_ID_1, DOCUMENT_ID_1),
        ("S2", CHUNK_ID_2, DOCUMENT_ID_2),
        ("S3", CHUNK_ID_3, DOCUMENT_ID_3),
    )[:source_count]
    sources = tuple(
        _source(citation_id, chunk_id, document_id)
        for citation_id, chunk_id, document_id in source_specs
    )
    items = tuple(_item(source) for source in sources)
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
        answer_text=answer_text,
        sources=sources,
        evidence=evidence,
        provider_model=provider_model,
        finish_reason=finish_reason,
        citations_validated=False,
    )


def _item(source: SourceReference) -> EvidenceItem:
    return EvidenceItem(
        citation_id=source.citation_id,
        chunk_id=source.chunk_id,
        document_id=source.document_id,
        filename=source.filename,
        page_number=source.page_number,
        text=f"Evidence for {source.citation_id}",
        reranker_score=1.0,
        retrieval_rank=source.page_number,
    )
