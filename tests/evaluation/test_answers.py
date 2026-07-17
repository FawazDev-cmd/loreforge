from uuid import UUID

import pytest

from loreforge.evaluation import (
    EvaluationCase,
    evaluate_answer,
    evaluate_citations,
    normalize_answer_text,
)
from loreforge.generation import (
    CitationValidationResult,
    EvidenceContext,
    EvidenceItem,
    GroundedAnswer,
    SourceReference,
    ValidatedGroundedAnswer,
)

ID1 = UUID("00000000-0000-0000-0000-000000000001")
ID2 = UUID("00000000-0000-0000-0000-000000000002")
DOC1 = UUID("00000000-0000-0000-0000-000000000101")
DOC2 = UUID("00000000-0000-0000-0000-000000000102")


def test_normalize_lowercase() -> None:
    assert normalize_answer_text("HELLO World") == "hello world"


def test_normalize_unicode_case_folding() -> None:
    assert normalize_answer_text("Stra" + chr(0x00DF) + "e") == "strasse"


def test_normalize_repeated_space_collapse() -> None:
    assert normalize_answer_text("one   two") == "one two"


def test_normalize_tabs_and_newlines() -> None:
    assert normalize_answer_text("one\ttwo\nthree") == "one two three"


def test_normalize_strips_edges() -> None:
    assert normalize_answer_text("  one two  ") == "one two"


def test_normalize_removes_one_citation() -> None:
    assert normalize_answer_text("Policy applies [S1].") == "policy applies ."


def test_normalize_removes_multiple_citations() -> None:
    assert normalize_answer_text("A [S1]. B [S2].") == "a . b ."


def test_normalize_removes_repeated_citations() -> None:
    assert normalize_answer_text("A [S1]. Again [S1].") == "a . again ."


def test_normalize_preserves_malformed_citation_markers() -> None:
    assert normalize_answer_text("A [S0] and [s1].") == "a [s0] and [s1]."


def test_normalize_preserves_punctuation() -> None:
    assert normalize_answer_text("Hello, world!") == "hello, world!"


def test_normalize_preserves_numbers() -> None:
    assert normalize_answer_text("There are 20 days.") == "there are 20 days."


def test_normalize_preserves_unicode_text() -> None:
    assert (
        normalize_answer_text("Caf" + chr(0x00E9) + " policy")
        == "caf" + chr(0x00E9) + " policy"
    )


def test_normalize_citation_only_text_returns_empty() -> None:
    assert normalize_answer_text("[S1]") == ""


@pytest.mark.parametrize("text", ["", "   "])
def test_normalize_blank_input_rejected(text: str) -> None:
    with pytest.raises(ValueError, match="text"):
        normalize_answer_text(text)


def test_normalize_repeated_calls_are_deterministic() -> None:
    text = "Policy [S1]."

    assert normalize_answer_text(text) == normalize_answer_text(text)


def test_normalize_input_remains_unchanged() -> None:
    text = "Policy [S1]."
    before = text

    normalize_answer_text(text)

    assert text == before


def test_evaluate_citations_exact_match() -> None:
    assert evaluate_citations(
        expected_citation_ids=("S1",), observed_citation_ids=("S1",)
    ) == (1.0, 1.0)


def test_evaluate_citations_subset_observed() -> None:
    precision, recall = evaluate_citations(
        expected_citation_ids=("S1", "S2"), observed_citation_ids=("S1",)
    )

    assert precision == 1.0
    assert recall == 0.5


def test_evaluate_citations_extra_observed() -> None:
    precision, recall = evaluate_citations(
        expected_citation_ids=("S1",), observed_citation_ids=("S1", "S2")
    )

    assert precision == 0.5
    assert recall == 1.0


def test_evaluate_citations_no_observed_with_expected_values() -> None:
    assert evaluate_citations(
        expected_citation_ids=("S1",), observed_citation_ids=()
    ) == (0.0, 0.0)


def test_evaluate_citations_both_empty() -> None:
    assert evaluate_citations(expected_citation_ids=(), observed_citation_ids=()) == (
        1.0,
        1.0,
    )


def test_evaluate_citations_expected_empty_observed_nonempty() -> None:
    assert evaluate_citations(
        expected_citation_ids=(), observed_citation_ids=("S1",)
    ) == (0.0, 1.0)


def test_evaluate_citations_order_does_not_change_set_metrics() -> None:
    first = evaluate_citations(
        expected_citation_ids=("S1", "S2"), observed_citation_ids=("S2", "S1")
    )
    second = evaluate_citations(
        expected_citation_ids=("S1", "S2"), observed_citation_ids=("S1", "S2")
    )

    assert first == second


def test_evaluate_citations_malformed_ids_rejected() -> None:
    with pytest.raises(ValueError, match="expected_citation_ids"):
        evaluate_citations(expected_citation_ids=("S0",), observed_citation_ids=())


def test_evaluate_citations_duplicate_ids_rejected() -> None:
    with pytest.raises(ValueError, match="observed_citation_ids"):
        evaluate_citations(
            expected_citation_ids=("S1",), observed_citation_ids=("S1", "S1")
        )


def test_evaluate_citations_is_deterministic() -> None:
    kwargs = {"expected_citation_ids": ("S1",), "observed_citation_ids": ("S1",)}

    assert evaluate_citations(**kwargs) == evaluate_citations(**kwargs)


def test_evaluate_citations_inputs_remain_unchanged() -> None:
    expected = ("S1",)
    observed = ("S1",)
    before = (expected, observed)

    evaluate_citations(expected_citation_ids=expected, observed_citation_ids=observed)

    assert (expected, observed) == before


def test_evaluate_answer_perfect_citation_metrics() -> None:
    metrics = evaluate_answer(
        case=_case(expected_citation_ids=("S1",)),
        answer=_validated_answer("Answer [S1]."),
    )

    assert metrics.citation_precision == 1.0
    assert metrics.citation_recall == 1.0


def test_evaluate_answer_missing_expected_citation_lowers_recall() -> None:
    metrics = evaluate_answer(
        case=_case(expected_citation_ids=("S1", "S2")),
        answer=_validated_answer("Answer [S1]."),
    )

    assert metrics.citation_recall == 0.5


def test_evaluate_answer_unnecessary_source_lowers_precision() -> None:
    metrics = evaluate_answer(
        case=_case(expected_citation_ids=("S1",)),
        answer=_validated_answer("Answer [S1] [S2].", citation_ids=("S1", "S2")),
    )

    assert metrics.citation_precision == 0.5


def test_evaluate_answer_exact_normalized_answer_match() -> None:
    metrics = evaluate_answer(
        case=_case(expected_answer="Employees receive twenty days."),
        answer=_validated_answer("Employees receive twenty days. [S1]"),
    )

    assert metrics.normalized_exact_match == 1.0


def test_evaluate_answer_citations_do_not_affect_exact_match() -> None:
    metrics = evaluate_answer(
        case=_case(expected_answer="Answer."), answer=_validated_answer("Answer. [S1]")
    )

    assert metrics.normalized_exact_match == 1.0


def test_evaluate_answer_case_differences_do_not_affect_exact_match() -> None:
    metrics = evaluate_answer(
        case=_case(expected_answer="ANSWER."), answer=_validated_answer("answer. [S1]")
    )

    assert metrics.normalized_exact_match == 1.0


def test_evaluate_answer_whitespace_differences_do_not_affect_exact_match() -> None:
    metrics = evaluate_answer(
        case=_case(expected_answer="Answer text."),
        answer=_validated_answer("Answer\n   text. [S1]"),
    )

    assert metrics.normalized_exact_match == 1.0


def test_evaluate_answer_punctuation_differences_fail_exact_match() -> None:
    metrics = evaluate_answer(
        case=_case(expected_answer="Answer text"),
        answer=_validated_answer("Answer text. [S1]"),
    )

    assert metrics.normalized_exact_match == 0.0


def test_evaluate_answer_word_order_differences_fail_exact_match() -> None:
    metrics = evaluate_answer(
        case=_case(expected_answer="one two"), answer=_validated_answer("two one [S1]")
    )

    assert metrics.normalized_exact_match == 0.0


def test_evaluate_answer_absent_expected_answer_returns_none() -> None:
    metrics = evaluate_answer(
        case=_case(expected_answer=None), answer=_validated_answer("Answer [S1].")
    )

    assert metrics.normalized_exact_match is None


def test_evaluate_answer_inputs_remain_unchanged() -> None:
    case = _case(expected_answer="Answer.")
    answer = _validated_answer("Answer. [S1]")
    before = (case, answer)

    evaluate_answer(case=case, answer=answer)

    assert (case, answer) == before


def _case(
    *,
    expected_citation_ids: tuple[str, ...] = ("S1",),
    expected_answer: str | None = "Answer.",
) -> EvaluationCase:
    return EvaluationCase(
        "case-1", "Question?", (ID1,), expected_citation_ids, expected_answer
    )


def _validated_answer(
    answer_text: str,
    *,
    citation_ids: tuple[str, ...] = ("S1",),
) -> ValidatedGroundedAnswer:
    sources = tuple(_source(citation_id) for citation_id in ("S1", "S2"))
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
    evidence = EvidenceContext(items, rendered_text, len(rendered_text), False)
    grounded = GroundedAnswer(
        "Question?", answer_text, sources, evidence, "model", "stop", True
    )
    validation = CitationValidationResult(citation_ids, citation_ids, (), False, True)
    cited_sources = tuple(
        source for source in sources if source.citation_id in set(citation_ids)
    )
    return ValidatedGroundedAnswer(grounded, validation, cited_sources)


def _source(citation_id: str) -> SourceReference:
    chunk_id = ID1 if citation_id == "S1" else ID2
    document_id = DOC1 if citation_id == "S1" else DOC2
    return SourceReference(
        citation_id, document_id, chunk_id, f"{citation_id}.pdf", int(citation_id[1:])
    )


def _item(source: SourceReference) -> EvidenceItem:
    return EvidenceItem(
        source.citation_id,
        source.chunk_id,
        source.document_id,
        source.filename,
        source.page_number,
        f"Evidence {source.citation_id}",
        1.0,
        source.page_number,
    )
