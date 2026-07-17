from dataclasses import FrozenInstanceError
from math import inf, nan
from uuid import UUID

import pytest

from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.generation import (
    EvidenceContext,
    EvidenceItem,
    GroundedAnswer,
    GroundedGenerationRequest,
    SourceReference,
)
from loreforge.reranking import RerankedSearchResult
from loreforge.retrieval import HybridSearchResult, RetrievalContribution

CHUNK_ID_1 = UUID("00000000-0000-0000-0000-000000000101")
CHUNK_ID_2 = UUID("00000000-0000-0000-0000-000000000102")
DOCUMENT_ID_1 = UUID("00000000-0000-0000-0000-000000000201")
DOCUMENT_ID_2 = UUID("00000000-0000-0000-0000-000000000202")


def test_grounded_generation_request_accepts_valid_defaults() -> None:
    request = GroundedGenerationRequest(question="question", candidates=(_candidate(),))

    assert request.question == "question"
    assert request.evidence_max_characters == 12000
    assert request.max_output_tokens == 800
    assert request.temperature == 0.0


def test_grounded_generation_request_accepts_valid_custom_settings() -> None:
    request = GroundedGenerationRequest(
        question="question",
        candidates=(_candidate(),),
        evidence_max_characters=500,
        max_output_tokens=64,
        temperature=0.7,
    )

    assert request.evidence_max_characters == 500
    assert request.max_output_tokens == 64
    assert request.temperature == 0.7


@pytest.mark.parametrize("question", ["", "   "])
def test_grounded_generation_request_rejects_blank_question(question: str) -> None:
    with pytest.raises(ValueError, match="question"):
        GroundedGenerationRequest(question=question, candidates=(_candidate(),))


def test_grounded_generation_request_rejects_empty_candidates() -> None:
    with pytest.raises(ValueError, match="candidates"):
        GroundedGenerationRequest(question="question", candidates=())


def test_grounded_generation_request_rejects_duplicate_chunk_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        GroundedGenerationRequest(
            question="question",
            candidates=(
                _candidate(chunk_id=CHUNK_ID_1, rank=1),
                _candidate(chunk_id=CHUNK_ID_1, rank=2),
            ),
        )


def test_grounded_generation_request_rejects_non_sequential_candidate_ranks() -> None:
    with pytest.raises(ValueError, match="sequential"):
        GroundedGenerationRequest(question="question", candidates=(_candidate(rank=2),))


@pytest.mark.parametrize("evidence_max_characters", [0, -1])
def test_grounded_generation_request_rejects_non_positive_evidence_budget(
    evidence_max_characters: int,
) -> None:
    with pytest.raises(ValueError, match="evidence_max_characters"):
        GroundedGenerationRequest(
            question="question",
            candidates=(_candidate(),),
            evidence_max_characters=evidence_max_characters,
        )


def test_grounded_generation_request_rejects_boolean_evidence_budget() -> None:
    with pytest.raises(ValueError, match="evidence_max_characters"):
        GroundedGenerationRequest(
            question="question",
            candidates=(_candidate(),),
            evidence_max_characters=True,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("max_output_tokens", [0, -1])
def test_grounded_generation_request_rejects_non_positive_output_tokens(
    max_output_tokens: int,
) -> None:
    with pytest.raises(ValueError, match="max_output_tokens"):
        GroundedGenerationRequest(
            question="question",
            candidates=(_candidate(),),
            max_output_tokens=max_output_tokens,
        )


def test_grounded_generation_request_rejects_boolean_output_tokens() -> None:
    with pytest.raises(ValueError, match="max_output_tokens"):
        GroundedGenerationRequest(
            question="question",
            candidates=(_candidate(),),
            max_output_tokens=True,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("temperature", [1, True])
def test_grounded_generation_request_rejects_invalid_temperature_types(
    temperature: object,
) -> None:
    with pytest.raises(ValueError, match="temperature"):
        GroundedGenerationRequest(
            question="question",
            candidates=(_candidate(),),
            temperature=temperature,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("temperature", [nan, inf, -inf])
def test_grounded_generation_request_rejects_non_finite_temperature(
    temperature: float,
) -> None:
    with pytest.raises(ValueError, match="finite"):
        GroundedGenerationRequest(
            question="question", candidates=(_candidate(),), temperature=temperature
        )


@pytest.mark.parametrize("temperature", [0.0, 2.0])
def test_grounded_generation_request_accepts_temperature_boundaries(
    temperature: float,
) -> None:
    request = GroundedGenerationRequest(
        question="question", candidates=(_candidate(),), temperature=temperature
    )

    assert request.temperature == temperature


@pytest.mark.parametrize("temperature", [-0.1, 2.1])
def test_grounded_generation_request_rejects_temperature_outside_range(
    temperature: float,
) -> None:
    with pytest.raises(ValueError, match="temperature"):
        GroundedGenerationRequest(
            question="question", candidates=(_candidate(),), temperature=temperature
        )


def test_grounded_generation_request_preserves_candidate_order() -> None:
    first = _candidate(chunk_id=CHUNK_ID_1, text="first", rank=1)
    second = _candidate(chunk_id=CHUNK_ID_2, text="second", rank=2)

    request = GroundedGenerationRequest(question="question", candidates=(first, second))

    assert request.candidates == (first, second)


def test_grounded_generation_request_is_immutable() -> None:
    request = GroundedGenerationRequest(question="question", candidates=(_candidate(),))

    with pytest.raises(FrozenInstanceError):
        request.question = "changed"


def test_source_reference_accepts_valid_values() -> None:
    source = _source_reference()

    assert source.citation_id == "S1"


@pytest.mark.parametrize("citation_id", ["", "1", "s1", "S", "S 1"])
def test_source_reference_rejects_invalid_citation_format(citation_id: str) -> None:
    with pytest.raises(ValueError, match="citation_id"):
        _source_reference(citation_id=citation_id)


def test_source_reference_rejects_zero_citation_number() -> None:
    with pytest.raises(ValueError, match="citation_id"):
        _source_reference(citation_id="S0")


@pytest.mark.parametrize("filename", ["", "   "])
def test_source_reference_rejects_blank_filename(filename: str) -> None:
    with pytest.raises(ValueError, match="filename"):
        _source_reference(filename=filename)


def test_source_reference_rejects_invalid_page_number() -> None:
    with pytest.raises(ValueError, match="page_number"):
        _source_reference(page_number=0)


def test_source_reference_is_immutable() -> None:
    source = _source_reference()

    with pytest.raises(FrozenInstanceError):
        source.filename = "changed.pdf"


def test_grounded_answer_accepts_valid_unvalidated_answer() -> None:
    answer = _grounded_answer()

    assert answer.citations_validated is False


def test_grounded_answer_accepts_validated_citations_for_day_18() -> None:
    answer = _grounded_answer(citations_validated=True)

    assert answer.citations_validated is True


@pytest.mark.parametrize("question", ["", "   "])
def test_grounded_answer_rejects_blank_question(question: str) -> None:
    with pytest.raises(ValueError, match="question"):
        _grounded_answer(question=question)


@pytest.mark.parametrize("answer_text", ["", "   "])
def test_grounded_answer_rejects_blank_answer(answer_text: str) -> None:
    with pytest.raises(ValueError, match="answer_text"):
        _grounded_answer(answer_text=answer_text)


def test_grounded_answer_rejects_empty_sources() -> None:
    with pytest.raises(ValueError, match="sources"):
        GroundedAnswer(
            question="question",
            answer_text="answer",
            sources=(),
            evidence=_evidence_context(),
            provider_model="model",
            finish_reason="stop",
            citations_validated=False,
        )


def test_grounded_answer_rejects_duplicate_citation_ids() -> None:
    evidence = _evidence_context(two_items=True)
    first = _source_reference(citation_id="S1", chunk_id=CHUNK_ID_1)
    second = _source_reference(citation_id="S1", chunk_id=CHUNK_ID_2)

    with pytest.raises(ValueError, match="unique"):
        _grounded_answer(evidence=evidence, sources=(first, second))


def test_grounded_answer_rejects_non_sequential_citation_ids() -> None:
    with pytest.raises(ValueError, match="sequential"):
        _grounded_answer(sources=(_source_reference(citation_id="S2"),))


def test_grounded_answer_rejects_duplicate_chunk_ids() -> None:
    evidence = _evidence_context(two_items=True)
    first = _source_reference(citation_id="S1", chunk_id=CHUNK_ID_1)
    second = _source_reference(citation_id="S2", chunk_id=CHUNK_ID_1)

    with pytest.raises(ValueError, match="chunk IDs"):
        _grounded_answer(evidence=evidence, sources=(first, second))


def test_grounded_answer_rejects_source_evidence_mismatch() -> None:
    source = _source_reference(filename="other.pdf")

    with pytest.raises(ValueError, match="evidence"):
        _grounded_answer(sources=(source,))


def test_grounded_answer_rejects_reordered_sources() -> None:
    evidence = _evidence_context(two_items=True)
    first = _source_reference(
        citation_id="S1",
        chunk_id=CHUNK_ID_2,
        document_id=DOCUMENT_ID_2,
        filename="two.pdf",
        page_number=2,
    )
    second = _source_reference(citation_id="S2", chunk_id=CHUNK_ID_1)

    with pytest.raises(ValueError, match="evidence"):
        _grounded_answer(evidence=evidence, sources=(first, second))


@pytest.mark.parametrize("provider_model", ["", "   "])
def test_grounded_answer_rejects_blank_provider_model(provider_model: str) -> None:
    with pytest.raises(ValueError, match="provider_model"):
        _grounded_answer(provider_model=provider_model)


@pytest.mark.parametrize("finish_reason", ["", "   "])
def test_grounded_answer_rejects_blank_finish_reason(finish_reason: str) -> None:
    with pytest.raises(ValueError, match="finish_reason"):
        _grounded_answer(finish_reason=finish_reason)


def test_grounded_answer_rejects_non_boolean_citation_state() -> None:
    with pytest.raises(ValueError, match="citations_validated"):
        _grounded_answer(citations_validated=0)  # type: ignore[arg-type]


def test_grounded_answer_retains_evidence_exactly() -> None:
    evidence = _evidence_context()

    answer = _grounded_answer(evidence=evidence)

    assert answer.evidence is evidence


def test_grounded_answer_is_immutable() -> None:
    answer = _grounded_answer()

    with pytest.raises(FrozenInstanceError):
        answer.answer_text = "changed"


def _grounded_answer(
    *,
    question: str = "question",
    answer_text: str = "answer",
    sources: tuple[SourceReference, ...] | None = None,
    evidence: EvidenceContext | None = None,
    provider_model: str = "model",
    finish_reason: str | None = "stop",
    citations_validated: bool = False,
) -> GroundedAnswer:
    context = evidence or _evidence_context()
    return GroundedAnswer(
        question=question,
        answer_text=answer_text,
        sources=sources or (_source_reference(),),
        evidence=context,
        provider_model=provider_model,
        finish_reason=finish_reason,
        citations_validated=citations_validated,
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


def _evidence_context(*, two_items: bool = False) -> EvidenceContext:
    first = _evidence_item()
    items = (first,)
    rendered_text = _rendered_for(first)
    if two_items:
        second = _evidence_item(
            citation_id="S2",
            chunk_id=CHUNK_ID_2,
            document_id=DOCUMENT_ID_2,
            filename="two.pdf",
            page_number=2,
            text="Second evidence.",
        )
        items = (first, second)
        rendered_text = f"{_rendered_for(first)}\n\n{_rendered_for(second)}"

    return EvidenceContext(
        items=items,
        rendered_text=rendered_text,
        total_characters=len(rendered_text),
        truncated=False,
    )


def _evidence_item(
    *,
    citation_id: str = "S1",
    chunk_id: UUID = CHUNK_ID_1,
    document_id: UUID = DOCUMENT_ID_1,
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


def _rendered_for(item: EvidenceItem) -> str:
    return (
        f"[{item.citation_id}]\n"
        f"Source: {item.filename}\n"
        f"Page: {item.page_number}\n"
        "Content:\n"
        f"{item.text}"
    )


def _source() -> DocumentSource:
    return DocumentSource(
        filename="sample.pdf", media_type="application/pdf", size_bytes=128
    )


def _chunk(
    *, chunk_id: UUID = CHUNK_ID_1, text: str = "Evidence text"
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_id=DOCUMENT_ID_1,
        source=_source(),
        page_number=1,
        chunk_index=0,
        text=text,
    )


def _candidate(
    *, chunk_id: UUID = CHUNK_ID_1, text: str = "Evidence text", rank: int = 1
) -> RerankedSearchResult:
    return RerankedSearchResult(
        hybrid_result=HybridSearchResult(
            chunk=_chunk(chunk_id=chunk_id, text=text),
            fused_score=1.0,
            rank=rank,
            contributions=(
                RetrievalContribution(strategy="semantic", rank=1, score=0.5),
            ),
        ),
        reranker_score=1.0,
        rank=rank,
    )
