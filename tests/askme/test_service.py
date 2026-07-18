from uuid import UUID

import pytest

from loreforge.askme import (
    AskMeGroundingError,
    AskMeRequest,
    AskMeService,
    AskMeUnavailableError,
    GroundedQueryEngine,
)
from loreforge.generation.answer_models import GroundedAnswer, SourceReference
from loreforge.generation.evidence import EvidenceContext, EvidenceItem
from loreforge.generation.validation_models import (
    CitationValidationResult,
    ValidatedGroundedAnswer,
)
from loreforge.query import NoRelevantEvidenceError, QueryExecutionError

REQUEST_ID = UUID("00000000-0000-0000-0000-000000000001")
REQUEST_ID_2 = UUID("00000000-0000-0000-0000-000000000002")
DOCUMENT_ID_1 = UUID("00000000-0000-0000-0000-000000000201")
DOCUMENT_ID_2 = UUID("00000000-0000-0000-0000-000000000202")
CHUNK_ID_1 = UUID("00000000-0000-0000-0000-000000000101")
CHUNK_ID_2 = UUID("00000000-0000-0000-0000-000000000102")
QUESTION = "What is the refund policy?"
ANSWER = "Refund requests must be submitted within 14 days [S1]."


class FakeEngine:
    def __init__(self, answer: ValidatedGroundedAnswer) -> None:
        self.answer_value = answer
        self.questions: list[str] = []

    def answer(self, question: str) -> ValidatedGroundedAnswer:
        self.questions.append(question)
        return self.answer_value


class RaisingEngine:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.questions: list[str] = []

    def answer(self, question: str) -> ValidatedGroundedAnswer:
        self.questions.append(question)
        raise self.error


class InvalidEngine:
    def __init__(self, answer: object) -> None:
        self.answer_value = answer

    def answer(self, question: str) -> ValidatedGroundedAnswer:
        return self.answer_value  # type: ignore[return-value]


class CountingFactory:
    def __init__(self, request_id: object = REQUEST_ID) -> None:
        self.request_id = request_id
        self.calls = 0

    def __call__(self) -> UUID:
        self.calls += 1
        return self.request_id  # type: ignore[return-value]


def test_protocol_compatible_fake_engine() -> None:
    assert isinstance(FakeEngine(_validated_answer()), GroundedQueryEngine)


def test_exact_question_passed_to_engine() -> None:
    question = "  What is the refund policy?  "
    engine = FakeEngine(_validated_answer(question=question))
    service = AskMeService(query_engine=engine, request_id_factory=lambda: REQUEST_ID)

    service.ask(AskMeRequest(question))

    assert engine.questions == [question]


def test_successful_validated_result_mapping() -> None:
    service = AskMeService(
        query_engine=FakeEngine(_validated_answer()),
        request_id_factory=lambda: REQUEST_ID,
    )

    result = service.ask(AskMeRequest(QUESTION))

    assert result.request_id == REQUEST_ID
    assert result.question == QUESTION
    assert result.answer == ANSWER
    assert [citation.citation_id for citation in result.citations] == ["S1"]


def test_exact_answer_text_preserved() -> None:
    answer_text = "  Refund requests must be submitted within 14 days [S1].  "
    service = AskMeService(
        query_engine=FakeEngine(_validated_answer(answer_text=answer_text)),
        request_id_factory=lambda: REQUEST_ID,
    )

    result = service.ask(AskMeRequest(QUESTION))

    assert result.answer == answer_text


def test_citation_order_preserved() -> None:
    service = AskMeService(
        query_engine=FakeEngine(
            _validated_answer(
                answer_text="Second source first [S2], first source second [S1].",
                citation_ids=("S2", "S1"),
                two_sources=True,
            )
        ),
        request_id_factory=lambda: REQUEST_ID,
    )

    result = service.ask(AskMeRequest(QUESTION))

    assert [citation.citation_id for citation in result.citations] == ["S2", "S1"]


def test_citation_metadata_mapped_correctly() -> None:
    service = AskMeService(
        query_engine=FakeEngine(_validated_answer()),
        request_id_factory=lambda: REQUEST_ID,
    )

    citation = service.ask(AskMeRequest(QUESTION)).citations[0]

    assert citation.document_id == DOCUMENT_ID_1
    assert citation.filename == "refund-policy.pdf"
    assert citation.page_number == 2
    assert citation.chunk_id == CHUNK_ID_1


def test_fixed_request_id_preserved() -> None:
    service = AskMeService(
        query_engine=FakeEngine(_validated_answer()),
        request_id_factory=lambda: REQUEST_ID_2,
    )

    assert service.ask(AskMeRequest(QUESTION)).request_id == REQUEST_ID_2


def test_request_id_factory_called_once_on_success() -> None:
    factory = CountingFactory()
    service = AskMeService(
        query_engine=FakeEngine(_validated_answer()),
        request_id_factory=factory,
    )

    service.ask(AskMeRequest(QUESTION))

    assert factory.calls == 1


def test_request_id_factory_not_called_on_engine_failure() -> None:
    error = RuntimeError("secret provider payload")
    factory = CountingFactory()
    service = AskMeService(
        query_engine=RaisingEngine(error),
        request_id_factory=factory,
    )

    with pytest.raises(AskMeUnavailableError):
        service.ask(AskMeRequest(QUESTION))

    assert factory.calls == 0


def test_mismatched_returned_question_rejected() -> None:
    service = AskMeService(
        query_engine=FakeEngine(_validated_answer(question="other question")),
        request_id_factory=lambda: REQUEST_ID,
    )

    with pytest.raises(AskMeGroundingError):
        service.ask(AskMeRequest(QUESTION))


def test_unvalidated_grounded_answer_rejected_if_structurally_returned() -> None:
    service = AskMeService(
        query_engine=InvalidEngine(_grounded_answer(citations_validated=False)),
        request_id_factory=lambda: REQUEST_ID,
    )

    with pytest.raises(AskMeGroundingError):
        service.ask(AskMeRequest(QUESTION))


def test_missing_cited_sources_rejected_if_structurally_returned() -> None:
    invalid_answer = object.__new__(ValidatedGroundedAnswer)
    object.__setattr__(invalid_answer, "grounded_answer", _grounded_answer())
    object.__setattr__(
        invalid_answer,
        "citation_validation",
        CitationValidationResult(("S1",), ("S1",), (), False, True),
    )
    object.__setattr__(invalid_answer, "cited_sources", ())
    service = AskMeService(
        query_engine=InvalidEngine(invalid_answer),
        request_id_factory=lambda: REQUEST_ID,
    )

    with pytest.raises(AskMeGroundingError):
        service.ask(AskMeRequest(QUESTION))


def test_invalid_request_id_factory_result_rejected() -> None:
    service = AskMeService(
        query_engine=FakeEngine(_validated_answer()),
        request_id_factory=CountingFactory("not-a-uuid"),
    )

    with pytest.raises(AskMeGroundingError):
        service.ask(AskMeRequest(QUESTION))


def test_no_relevant_evidence_error_maps_to_grounding_error() -> None:
    service = AskMeService(
        query_engine=RaisingEngine(NoRelevantEvidenceError("raw evidence detail"))
    )
    factory = CountingFactory()
    service = AskMeService(
        query_engine=RaisingEngine(NoRelevantEvidenceError("raw evidence detail")),
        request_id_factory=factory,
    )

    with pytest.raises(AskMeGroundingError) as exc_info:
        service.ask(AskMeRequest(QUESTION))

    assert "raw evidence detail" not in str(exc_info.value)
    assert factory.calls == 0


def test_query_execution_error_maps_to_unavailable_error() -> None:
    factory = CountingFactory()
    service = AskMeService(
        query_engine=RaisingEngine(QueryExecutionError("raw provider detail")),
        request_id_factory=factory,
    )

    with pytest.raises(AskMeUnavailableError) as exc_info:
        service.ask(AskMeRequest(QUESTION))

    assert "raw provider detail" not in str(exc_info.value)
    assert factory.calls == 0


def test_existing_unavailable_error_propagated_unchanged() -> None:
    error = AskMeUnavailableError("internal unavailable")
    service = AskMeService(query_engine=RaisingEngine(error))

    with pytest.raises(AskMeUnavailableError) as exc_info:
        service.ask(AskMeRequest(QUESTION))

    assert exc_info.value is error


def test_existing_grounding_error_propagated_unchanged() -> None:
    error = AskMeGroundingError("internal grounding")
    service = AskMeService(query_engine=RaisingEngine(error))

    with pytest.raises(AskMeGroundingError) as exc_info:
        service.ask(AskMeRequest(QUESTION))

    assert exc_info.value is error


def test_unexpected_engine_exception_mapped_to_unavailable() -> None:
    service = AskMeService(query_engine=RaisingEngine(RuntimeError("provider secret")))

    with pytest.raises(AskMeUnavailableError) as exc_info:
        service.ask(AskMeRequest(QUESTION))

    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_raw_unexpected_exception_message_not_copied() -> None:
    service = AskMeService(query_engine=RaisingEngine(RuntimeError("provider secret")))

    with pytest.raises(AskMeUnavailableError) as exc_info:
        service.ask(AskMeRequest(QUESTION))

    assert "provider secret" not in str(exc_info.value)


def test_input_and_engine_output_remain_unchanged() -> None:
    request = AskMeRequest(QUESTION)
    validated = _validated_answer()
    before = validated
    service = AskMeService(
        query_engine=FakeEngine(validated),
        request_id_factory=lambda: REQUEST_ID,
    )

    service.ask(request)

    assert request == AskMeRequest(QUESTION)
    assert validated == before


def test_deterministic_repeated_runs_with_deterministic_factories() -> None:
    def run() -> object:
        service = AskMeService(
            query_engine=FakeEngine(_validated_answer()),
            request_id_factory=lambda: REQUEST_ID,
        )
        return service.ask(AskMeRequest(QUESTION))

    assert run() == run()


def _validated_answer(
    *,
    question: str = QUESTION,
    answer_text: str = ANSWER,
    citation_ids: tuple[str, ...] = ("S1",),
    two_sources: bool = False,
) -> ValidatedGroundedAnswer:
    grounded_answer = _grounded_answer(
        question=question,
        answer_text=answer_text,
        two_sources=two_sources,
    )
    source_by_id = {source.citation_id: source for source in grounded_answer.sources}
    return ValidatedGroundedAnswer(
        grounded_answer=grounded_answer,
        citation_validation=CitationValidationResult(
            citation_ids=citation_ids,
            supported_citation_ids=citation_ids,
            unsupported_citation_ids=(),
            missing_citations=False,
            is_valid=True,
        ),
        cited_sources=tuple(source_by_id[citation_id] for citation_id in citation_ids),
    )


def _grounded_answer(
    *,
    question: str = QUESTION,
    answer_text: str = ANSWER,
    citations_validated: bool = True,
    two_sources: bool = False,
) -> GroundedAnswer:
    first = _source_reference()
    sources = (first,)
    items = (_evidence_item(),)
    if two_sources:
        second = _source_reference(
            citation_id="S2",
            document_id=DOCUMENT_ID_2,
            chunk_id=CHUNK_ID_2,
            filename="shipping-policy.pdf",
            page_number=5,
        )
        sources = (first, second)
        items = (
            items[0],
            _evidence_item(
                citation_id="S2",
                document_id=DOCUMENT_ID_2,
                chunk_id=CHUNK_ID_2,
                filename="shipping-policy.pdf",
                page_number=5,
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
    return GroundedAnswer(
        question=question,
        answer_text=answer_text,
        sources=sources,
        evidence=EvidenceContext(
            items=items,
            rendered_text=rendered_text,
            total_characters=len(rendered_text),
            truncated=False,
        ),
        provider_model="offline-test-model",
        finish_reason="stop",
        citations_validated=citations_validated,
    )


def _source_reference(
    *,
    citation_id: str = "S1",
    document_id: UUID = DOCUMENT_ID_1,
    chunk_id: UUID = CHUNK_ID_1,
    filename: str = "refund-policy.pdf",
    page_number: int = 2,
) -> SourceReference:
    return SourceReference(
        citation_id=citation_id,
        document_id=document_id,
        chunk_id=chunk_id,
        filename=filename,
        page_number=page_number,
    )


def _evidence_item(
    *,
    citation_id: str = "S1",
    document_id: UUID = DOCUMENT_ID_1,
    chunk_id: UUID = CHUNK_ID_1,
    filename: str = "refund-policy.pdf",
    page_number: int = 2,
) -> EvidenceItem:
    return EvidenceItem(
        citation_id=citation_id,
        chunk_id=chunk_id,
        document_id=document_id,
        filename=filename,
        page_number=page_number,
        text="Evidence text",
        reranker_score=1.0,
        retrieval_rank=1,
    )
