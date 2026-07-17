from uuid import UUID

import pytest

from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.generation import (
    EvidenceContext,
    EvidenceContextError,
    GenerationRequest,
    GenerationResponse,
    GroundedAnswer,
    GroundedGenerationRequest,
    generate_grounded_answer,
    source_references_from_evidence,
)
from loreforge.reranking import RerankedSearchResult
from loreforge.retrieval import HybridSearchResult, RetrievalContribution

CHUNK_ID_1 = UUID("00000000-0000-0000-0000-000000000101")
CHUNK_ID_2 = UUID("00000000-0000-0000-0000-000000000102")
DOCUMENT_ID_1 = UUID("00000000-0000-0000-0000-000000000201")
DOCUMENT_ID_2 = UUID("00000000-0000-0000-0000-000000000202")


class RecordingProvider:
    def __init__(
        self,
        response: GenerationResponse | None = None,
    ) -> None:
        self.response = response or GenerationResponse(
            text="Employees receive twenty days of leave.",
            model="fake-model",
            finish_reason="stop",
        )
        self.calls: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        self.calls.append(request)
        return self.response


class FailingProvider:
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        raise RuntimeError("provider failed")


def test_source_conversion_one_evidence_item_creates_one_source() -> None:
    evidence = _evidence_context()

    sources = source_references_from_evidence(evidence)

    assert len(sources) == 1
    assert sources[0].citation_id == "S1"


def test_source_conversion_multiple_items_preserve_order() -> None:
    evidence = _evidence_context(two_items=True)

    sources = source_references_from_evidence(evidence)

    assert [source.citation_id for source in sources] == ["S1", "S2"]


def test_source_conversion_copies_every_required_field() -> None:
    evidence = _evidence_context()

    source = source_references_from_evidence(evidence)[0]
    item = evidence.items[0]

    assert source.citation_id == item.citation_id
    assert source.document_id == item.document_id
    assert source.chunk_id == item.chunk_id
    assert source.filename == item.filename
    assert source.page_number == item.page_number


def test_source_conversion_returns_tuple() -> None:
    assert isinstance(source_references_from_evidence(_evidence_context()), tuple)


def test_source_conversion_is_deterministic() -> None:
    evidence = _evidence_context(two_items=True)

    first = source_references_from_evidence(evidence)
    second = source_references_from_evidence(evidence)

    assert first == second


def test_source_conversion_does_not_mutate_evidence() -> None:
    evidence = _evidence_context(two_items=True)
    before = evidence

    source_references_from_evidence(evidence)

    assert evidence == before


def test_generate_grounded_answer_successful_end_to_end() -> None:
    provider = RecordingProvider()

    answer = generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="What is leave?", candidates=(_candidate(),)
        ),
        provider=provider,
    )

    assert isinstance(answer, GroundedAnswer)
    assert answer.answer_text == "Employees receive twenty days of leave."


def test_generate_grounded_answer_preserves_original_question_exactly() -> None:
    question = "  What is leave?  "

    answer = generate_grounded_answer(
        request=GroundedGenerationRequest(
            question=question, candidates=(_candidate(),)
        ),
        provider=RecordingProvider(),
    )

    assert answer.question == question


def test_generate_grounded_answer_builds_evidence_context_from_candidates() -> None:
    candidate = _candidate(
        filename="policy.pdf", page_number=3, text="Leave is twenty days."
    )

    answer = generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="What is leave?", candidates=(candidate,)
        ),
        provider=RecordingProvider(),
    )

    assert answer.evidence.items[0].filename == "policy.pdf"
    assert answer.evidence.items[0].page_number == 3
    assert answer.evidence.items[0].text == "Leave is twenty days."


def test_generate_grounded_answer_assigns_deterministic_citation_ids() -> None:
    answer = generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question",
            candidates=(
                _candidate(chunk_id=CHUNK_ID_1, rank=1),
                _candidate(chunk_id=CHUNK_ID_2, document_id=DOCUMENT_ID_2, rank=2),
            ),
        ),
        provider=RecordingProvider(),
    )

    assert [source.citation_id for source in answer.sources] == ["S1", "S2"]


def test_generate_grounded_answer_prompt_contains_included_evidence() -> None:
    provider = RecordingProvider()

    generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question", candidates=(_candidate(text="Included evidence."),)
        ),
        provider=provider,
    )

    assert "Included evidence." in provider.calls[0].user_prompt


def test_generate_grounded_answer_provider_receives_separate_prompts() -> None:
    provider = RecordingProvider()

    generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question", candidates=(_candidate(),)
        ),
        provider=provider,
    )

    assert provider.calls[0].system_prompt.startswith("You are AskMe")
    assert provider.calls[0].user_prompt.startswith("Question:\nquestion")


def test_generate_grounded_answer_forwards_output_token_limit() -> None:
    provider = RecordingProvider()

    generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question", candidates=(_candidate(),), max_output_tokens=123
        ),
        provider=provider,
    )

    assert provider.calls[0].max_output_tokens == 123


def test_generate_grounded_answer_forwards_temperature() -> None:
    provider = RecordingProvider()

    generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question", candidates=(_candidate(),), temperature=0.8
        ),
        provider=provider,
    )

    assert provider.calls[0].temperature == 0.8


def test_generate_grounded_answer_calls_provider_once() -> None:
    provider = RecordingProvider()

    generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question", candidates=(_candidate(),)
        ),
        provider=provider,
    )

    assert len(provider.calls) == 1


def test_generate_grounded_answer_preserves_generated_text_exactly() -> None:
    text = "  Exact answer text.\n"
    provider = RecordingProvider(
        GenerationResponse(text=text, model="fake-model", finish_reason="stop")
    )

    answer = generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question", candidates=(_candidate(),)
        ),
        provider=provider,
    )

    assert answer.answer_text == text


def test_generate_grounded_answer_preserves_provider_model() -> None:
    provider = RecordingProvider(
        GenerationResponse(text="answer", model="provider-model", finish_reason="stop")
    )

    answer = generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question", candidates=(_candidate(),)
        ),
        provider=provider,
    )

    assert answer.provider_model == "provider-model"


def test_generate_grounded_answer_preserves_finish_reason() -> None:
    provider = RecordingProvider(
        GenerationResponse(text="answer", model="model", finish_reason="length")
    )

    answer = generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question", candidates=(_candidate(),)
        ),
        provider=provider,
    )

    assert answer.finish_reason == "length"


def test_generate_grounded_answer_accepts_none_finish_reason() -> None:
    provider = RecordingProvider(
        GenerationResponse(text="answer", model="model", finish_reason=None)
    )

    answer = generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question", candidates=(_candidate(),)
        ),
        provider=provider,
    )

    assert answer.finish_reason is None


def test_generate_grounded_answer_citations_validated_is_false() -> None:
    answer = generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question", candidates=(_candidate(),)
        ),
        provider=RecordingProvider(),
    )

    assert answer.citations_validated is False


def test_generate_grounded_answer_all_included_evidence_produces_sources() -> None:
    answer = generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question",
            candidates=(
                _candidate(chunk_id=CHUNK_ID_1, rank=1),
                _candidate(chunk_id=CHUNK_ID_2, document_id=DOCUMENT_ID_2, rank=2),
            ),
        ),
        provider=RecordingProvider(),
    )

    assert len(answer.sources) == 2


def test_generate_grounded_answer_budget_omission_removes_sources() -> None:
    first = _candidate(chunk_id=CHUNK_ID_1, text="Alpha", rank=1)
    second = _candidate(
        chunk_id=CHUNK_ID_2, document_id=DOCUMENT_ID_2, text="Beta", rank=2
    )
    first_block = "[S1]\nSource: sample.pdf\nPage: 1\nContent:\nAlpha"

    answer = generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question",
            candidates=(first, second),
            evidence_max_characters=len(first_block),
        ),
        provider=RecordingProvider(),
    )

    assert [source.chunk_id for source in answer.sources] == [CHUNK_ID_1]
    assert "Beta" not in answer.evidence.rendered_text


def test_generate_grounded_answer_preserves_budget_truncation_state() -> None:
    first = _candidate(chunk_id=CHUNK_ID_1, text="Alpha", rank=1)
    second = _candidate(
        chunk_id=CHUNK_ID_2, document_id=DOCUMENT_ID_2, text="Beta", rank=2
    )
    first_block = "[S1]\nSource: sample.pdf\nPage: 1\nContent:\nAlpha"

    answer = generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question",
            candidates=(first, second),
            evidence_max_characters=len(first_block),
        ),
        provider=RecordingProvider(),
    )

    assert answer.evidence.truncated is True


def test_generate_grounded_answer_does_not_mutate_candidates() -> None:
    candidates = (_candidate(),)
    before = candidates

    generate_grounded_answer(
        request=GroundedGenerationRequest(question="question", candidates=candidates),
        provider=RecordingProvider(),
    )

    assert candidates == before


def test_generate_grounded_answer_is_deterministic_with_fake_provider() -> None:
    request = GroundedGenerationRequest(question="question", candidates=(_candidate(),))

    first = generate_grounded_answer(request=request, provider=RecordingProvider())
    second = generate_grounded_answer(request=request, provider=RecordingProvider())

    assert first == second


def test_generate_grounded_answer_provider_errors_propagate_unchanged() -> None:
    with pytest.raises(RuntimeError, match="provider failed"):
        generate_grounded_answer(
            request=GroundedGenerationRequest(
                question="question", candidates=(_candidate(),)
            ),
            provider=FailingProvider(),
        )


def test_generate_grounded_answer_evidence_budget_errors_propagate_unchanged() -> None:
    with pytest.raises(EvidenceContextError, match="budget"):
        generate_grounded_answer(
            request=GroundedGenerationRequest(
                question="question",
                candidates=(_candidate(),),
                evidence_max_characters=1,
            ),
            provider=RecordingProvider(),
        )


def test_generate_grounded_answer_does_not_parse_missing_citations() -> None:
    provider = RecordingProvider(
        GenerationResponse(
            text="Employees receive twenty days of leave.",
            model="model",
            finish_reason="stop",
        )
    )

    answer = generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question", candidates=(_candidate(),)
        ),
        provider=provider,
    )

    assert answer.answer_text == "Employees receive twenty days of leave."
    assert answer.citations_validated is False


def test_generate_grounded_answer_does_not_reject_unsupported_citation_syntax() -> None:
    provider = RecordingProvider(
        GenerationResponse(
            text="Employees receive twenty days of leave [S99].",
            model="model",
            finish_reason="stop",
        )
    )

    answer = generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question", candidates=(_candidate(),)
        ),
        provider=provider,
    )

    assert answer.answer_text == "Employees receive twenty days of leave [S99]."
    assert answer.citations_validated is False


def test_generate_grounded_answer_generation_functions_called_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import loreforge.generation.orchestration as orchestration

    calls = {"evidence": 0, "prompt": 0, "request": 0}
    original_build_evidence = orchestration.build_evidence_context
    original_build_prompt = orchestration.build_grounded_prompt
    original_generation_request = orchestration.generation_request_from_prompt

    def spy_build_evidence_context(*args: object, **kwargs: object) -> EvidenceContext:
        calls["evidence"] += 1
        return original_build_evidence(*args, **kwargs)

    def spy_build_grounded_prompt(*args: object, **kwargs: object) -> object:
        calls["prompt"] += 1
        return original_build_prompt(*args, **kwargs)

    def spy_generation_request_from_prompt(*args: object, **kwargs: object) -> object:
        calls["request"] += 1
        return original_generation_request(*args, **kwargs)

    monkeypatch.setattr(
        orchestration, "build_evidence_context", spy_build_evidence_context
    )
    monkeypatch.setattr(
        orchestration, "build_grounded_prompt", spy_build_grounded_prompt
    )
    monkeypatch.setattr(
        orchestration,
        "generation_request_from_prompt",
        spy_generation_request_from_prompt,
    )

    generate_grounded_answer(
        request=GroundedGenerationRequest(
            question="question", candidates=(_candidate(),)
        ),
        provider=RecordingProvider(),
    )

    assert calls == {"evidence": 1, "prompt": 1, "request": 1}


def _evidence_context(*, two_items: bool = False) -> EvidenceContext:
    items = (
        _evidence_item(
            citation_id="S1",
            chunk_id=CHUNK_ID_1,
            document_id=DOCUMENT_ID_1,
            filename="sample.pdf",
            page_number=1,
            text="Evidence text",
        ),
    )
    if two_items:
        items = (
            items[0],
            _evidence_item(
                citation_id="S2",
                chunk_id=CHUNK_ID_2,
                document_id=DOCUMENT_ID_2,
                filename="second.pdf",
                page_number=2,
                text="Second evidence",
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
    return EvidenceContext(
        items=items,
        rendered_text=rendered_text,
        total_characters=len(rendered_text),
        truncated=False,
    )


def _evidence_item(
    *,
    citation_id: str,
    chunk_id: UUID,
    document_id: UUID,
    filename: str,
    page_number: int,
    text: str,
):
    from loreforge.generation import EvidenceItem

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


def _source(*, filename: str = "sample.pdf") -> DocumentSource:
    return DocumentSource(
        filename=filename, media_type="application/pdf", size_bytes=128
    )


def _chunk(
    *,
    chunk_id: UUID = CHUNK_ID_1,
    document_id: UUID = DOCUMENT_ID_1,
    filename: str = "sample.pdf",
    page_number: int = 1,
    text: str = "Evidence text",
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        source=_source(filename=filename),
        page_number=page_number,
        chunk_index=0,
        text=text,
    )


def _candidate(
    *,
    chunk_id: UUID = CHUNK_ID_1,
    document_id: UUID = DOCUMENT_ID_1,
    filename: str = "sample.pdf",
    page_number: int = 1,
    text: str = "Evidence text",
    rank: int = 1,
) -> RerankedSearchResult:
    return RerankedSearchResult(
        hybrid_result=HybridSearchResult(
            chunk=_chunk(
                chunk_id=chunk_id,
                document_id=document_id,
                filename=filename,
                page_number=page_number,
                text=text,
            ),
            fused_score=1.0,
            rank=rank,
            contributions=(
                RetrievalContribution(strategy="semantic", rank=1, score=0.5),
            ),
        ),
        reranker_score=1.0,
        rank=rank,
    )
