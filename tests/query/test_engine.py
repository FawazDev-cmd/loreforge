from datetime import datetime, timezone
from uuid import UUID

import pytest

from loreforge.askme import GroundedQueryEngine
from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.embeddings import EmbeddingVector
from loreforge.generation import (
    EvidenceContext,
    EvidenceContextConfig,
    EvidenceItem,
    GenerationRequest,
    GenerationResponse,
    GroundedAnswer,
    PromptPackage,
    ValidatedGroundedAnswer,
    validate_grounded_answer,
)
from loreforge.observability import (
    InMemoryMetricsRecorder,
    InMemoryOperationalMetricsRecorder,
)
from loreforge.query import (
    NoRelevantEvidenceError,
    ProductionGroundedQueryEngine,
    QueryCompositionError,
    QueryExecutionError,
)
from loreforge.reranking import (
    RerankedSearchResponse,
    RerankedSearchResult,
    RerankerProvider,
    RerankingRequest,
    RerankingScore,
)
from loreforge.retrieval import (
    HybridSearchResult,
    LexicalSearchRequest,
    LexicalSearchResponse,
    LexicalSearchResult,
    RetrievalContribution,
)
from loreforge.vector_index import IndexedVector, VectorSearchResult

QUESTION = "What is the refund policy?"
ANSWER = "Refund requests must be submitted within 14 days [S1]."
QUERY_ID = UUID("00000000-0000-0000-0000-000000000001")
DOCUMENT_ID_1 = UUID("00000000-0000-0000-0000-000000000201")
DOCUMENT_ID_2 = UUID("00000000-0000-0000-0000-000000000202")
CHUNK_ID_1 = UUID("00000000-0000-0000-0000-000000000101")
CHUNK_ID_2 = UUID("00000000-0000-0000-0000-000000000102")


class FakeQueryEmbedder:
    def __init__(self, call_log: list[str], fail: bool = False) -> None:
        self.call_log = call_log
        self.fail = fail
        self.questions: list[str] = []

    def embed_query(self, question: str) -> EmbeddingVector:
        self.call_log.append("embed")
        self.questions.append(question)
        if self.fail:
            raise RuntimeError("raw embedding details")
        return EmbeddingVector(item_id=QUERY_ID, values=(0.25, 0.75))


class FakeSemanticRetriever:
    def __init__(
        self,
        call_log: list[str],
        results: tuple[VectorSearchResult, ...] | None = None,
        fail: bool = False,
    ) -> None:
        self.call_log = call_log
        self.results = _semantic_results() if results is None else results
        self.fail = fail
        self.received_vectors: list[tuple[float, ...]] = []
        self.received_top_k: list[int] = []

    def search(
        self,
        *,
        query_vector: tuple[float, ...],
        top_k: int,
    ) -> tuple[VectorSearchResult, ...]:
        self.call_log.append("semantic")
        self.received_vectors.append(query_vector)
        self.received_top_k.append(top_k)
        if self.fail:
            raise RuntimeError("raw semantic details")
        return self.results[:top_k]


class FakeLexicalRetriever:
    def __init__(
        self,
        call_log: list[str],
        results: tuple[LexicalSearchResult, ...] | None = None,
        fail: bool = False,
    ) -> None:
        self.call_log = call_log
        self.results = _lexical_results() if results is None else results
        self.fail = fail
        self.requests: list[LexicalSearchRequest] = []

    def search(self, request: LexicalSearchRequest) -> LexicalSearchResponse:
        self.call_log.append("lexical")
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("raw lexical details")
        return LexicalSearchResponse(
            query=request.query, results=self.results[: request.top_k]
        )


class FakeRerankerProvider:
    def __init__(self, call_log: list[str], fail: bool = False) -> None:
        self.call_log = call_log
        self.fail = fail
        self.requests: list[tuple[RerankingRequest, ...]] = []

    def score(
        self,
        requests: tuple[RerankingRequest, ...],
    ) -> tuple[RerankingScore, ...]:
        self.call_log.append("reranker")
        self.requests.append(requests)
        if self.fail:
            raise RuntimeError("raw reranker details")
        return tuple(
            RerankingScore(item_id=request.item_id, score=float(len(requests) - index))
            for index, request in enumerate(requests)
        )


class FakeGenerator:
    def __init__(self, call_log: list[str], fail: bool = False) -> None:
        self.call_log = call_log
        self.fail = fail
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        self.call_log.append("generator")
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("raw generation details")
        return GenerationResponse(
            text=ANSWER, model="offline-model", finish_reason="stop"
        )


class EngineParts:
    def __init__(self, *, fail_at: str | None = None) -> None:
        self.call_log: list[str] = []
        self.embedder = FakeQueryEmbedder(self.call_log, fail=fail_at == "embed")
        self.semantic = FakeSemanticRetriever(self.call_log, fail=fail_at == "semantic")
        self.lexical = FakeLexicalRetriever(self.call_log, fail=fail_at == "lexical")
        self.reranker = FakeRerankerProvider(self.call_log, fail=fail_at == "reranker")
        self.generator = FakeGenerator(self.call_log, fail=fail_at == "generator")
        self.hybrid_inputs: list[
            tuple[tuple[VectorSearchResult, ...], tuple[LexicalSearchResult, ...]]
        ] = []
        self.evidence_inputs: list[tuple[RerankedSearchResult, ...]] = []
        self.prompt_inputs: list[tuple[str, EvidenceContext]] = []
        self.citation_inputs: list[GroundedAnswer] = []
        self.fail_at = fail_at

    def engine(
        self,
        *,
        metrics_recorder: InMemoryMetricsRecorder | None = None,
        operational_metrics: InMemoryOperationalMetricsRecorder | None = None,
        monotonic_clock: "FakeMonotonicClock | None" = None,
        utc_clock: "FakeUtcClock | None" = None,
    ) -> ProductionGroundedQueryEngine:
        return ProductionGroundedQueryEngine(
            query_embedder=self.embedder,
            semantic_retriever=self.semantic,  # type: ignore[arg-type]
            lexical_retriever=self.lexical,  # type: ignore[arg-type]
            hybrid_fuser=self.hybrid_fuser,
            reranker=self.reranker,
            reranking_stage=self.reranking_stage,
            evidence_builder=self.evidence_builder,
            prompt_builder=self.prompt_builder,
            answer_generator=self.generator,
            citation_enforcer=self.citation_enforcer,
            metrics_recorder=metrics_recorder,
            operational_metrics=operational_metrics,
            trace_id_factory=lambda: UUID("00000000-0000-0000-0000-000000000901"),
            monotonic_clock=monotonic_clock,
            utc_clock=utc_clock,
            semantic_top_k=4,
            lexical_top_k=3,
            hybrid_top_k=2,
            rerank_top_k=2,
            rrf_k=11,
        )

    def hybrid_fuser(
        self,
        semantic_results: tuple[VectorSearchResult, ...],
        lexical_results: tuple[LexicalSearchResult, ...],
        top_k: int,
        rrf_k: int,
    ) -> tuple[HybridSearchResult, ...]:
        self.call_log.append("hybrid")
        self.hybrid_inputs.append((semantic_results, lexical_results))
        if self.fail_at == "hybrid":
            raise RuntimeError("raw hybrid details")
        return _hybrid_results()[:top_k]

    def reranking_stage(
        self,
        question: str,
        candidates: tuple[HybridSearchResult, ...],
        provider: RerankerProvider,
        top_k: int,
    ) -> RerankedSearchResponse:
        requests = tuple(
            RerankingRequest(
                item_id=candidate.chunk.chunk_id,
                query=question,
                passage=candidate.chunk.text,
            )
            for candidate in candidates
        )
        scores = provider.score(requests)
        ranked = tuple(
            RerankedSearchResult(
                hybrid_result=candidate,
                reranker_score=score.score,
                rank=rank,
            )
            for rank, (candidate, score) in enumerate(
                zip(candidates, scores, strict=True), start=1
            )
        )
        return RerankedSearchResponse(question=question, results=ranked[:top_k])

    def evidence_builder(
        self,
        candidates: tuple[RerankedSearchResult, ...],
        config: EvidenceContextConfig,
    ) -> EvidenceContext:
        self.call_log.append("evidence")
        self.evidence_inputs.append(candidates)
        if self.fail_at == "evidence":
            raise RuntimeError("raw evidence details")
        items = tuple(
            EvidenceItem(
                citation_id=f"S{index}",
                chunk_id=candidate.hybrid_result.chunk.chunk_id,
                document_id=candidate.hybrid_result.chunk.document_id,
                filename=candidate.hybrid_result.chunk.source.filename,
                page_number=candidate.hybrid_result.chunk.page_number,
                text=candidate.hybrid_result.chunk.text,
                reranker_score=candidate.reranker_score,
                retrieval_rank=candidate.rank,
            )
            for index, candidate in enumerate(candidates, start=1)
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

    def prompt_builder(self, question: str, evidence: EvidenceContext) -> PromptPackage:
        self.call_log.append("prompt")
        self.prompt_inputs.append((question, evidence))
        if self.fail_at == "prompt":
            raise RuntimeError("raw prompt details")
        return PromptPackage(
            system_prompt="system prompt",
            user_prompt=f"Question:\n{question}\n\nEvidence:\n{evidence.rendered_text}",
            evidence=evidence,
        )

    def citation_enforcer(self, answer: GroundedAnswer) -> ValidatedGroundedAnswer:
        self.call_log.append("citations")
        self.citation_inputs.append(answer)
        if self.fail_at == "citations":
            raise RuntimeError("raw citation details")
        return validate_grounded_answer(answer)


def test_engine_satisfies_grounded_query_protocol() -> None:
    assert isinstance(EngineParts().engine(), GroundedQueryEngine)


def test_successful_flow_calls_collaborators_with_existing_contracts() -> None:
    parts = EngineParts()

    result = parts.engine().answer(QUESTION)

    assert parts.embedder.questions == [QUESTION]
    assert parts.semantic.received_vectors == [(0.25, 0.75)]
    assert parts.semantic.received_top_k == [4]
    assert parts.lexical.requests == [LexicalSearchRequest(query=QUESTION, top_k=3)]
    assert parts.hybrid_inputs == [(_semantic_results(), _lexical_results())]
    assert [request.query for request in parts.reranker.requests[0]] == [
        QUESTION,
        QUESTION,
    ]
    assert parts.evidence_inputs[0][0].hybrid_result.chunk == _chunk_one()
    assert parts.prompt_inputs[0][0] == QUESTION
    assert parts.generator.requests[0].system_prompt == "system prompt"
    assert parts.citation_inputs[0].evidence == parts.prompt_inputs[0][1]
    assert isinstance(result, ValidatedGroundedAnswer)


def test_successful_flow_preserves_answer_question_citations_and_source_identity() -> (
    None
):
    result = EngineParts().engine().answer(QUESTION)

    assert result.grounded_answer.question == QUESTION
    assert result.grounded_answer.answer_text == ANSWER
    assert [source.citation_id for source in result.cited_sources] == ["S1"]
    source = result.cited_sources[0]
    assert source.document_id == DOCUMENT_ID_1
    assert source.chunk_id == CHUNK_ID_1
    assert source.filename == "refund-policy.pdf"
    assert source.page_number == 2


def test_pipeline_call_order() -> None:
    parts = EngineParts()

    parts.engine().answer(QUESTION)

    assert parts.call_log == [
        "embed",
        "semantic",
        "lexical",
        "hybrid",
        "reranker",
        "evidence",
        "prompt",
        "generator",
        "citations",
    ]


@pytest.mark.parametrize("question", ["", "   "])
def test_blank_question_rejected(question: str) -> None:
    with pytest.raises(QueryCompositionError, match="question"):
        EngineParts().engine().answer(question)


def test_non_string_question_rejected() -> None:
    with pytest.raises(QueryCompositionError, match="question"):
        EngineParts().engine().answer(123)  # type: ignore[arg-type]


def test_valid_surrounding_whitespace_preserved() -> None:
    question = "  What is the refund policy?  "
    parts = EngineParts()

    parts.engine().answer(question)

    assert parts.embedder.questions == [question]
    assert parts.lexical.requests[0].query == question
    assert parts.prompt_inputs[0][0] == question


def test_both_retrieval_sources_empty_short_circuits_before_generation() -> None:
    parts = EngineParts()
    parts.semantic.results = ()
    parts.lexical.results = ()

    with pytest.raises(NoRelevantEvidenceError):
        parts.engine().answer(QUESTION)

    assert parts.call_log == ["embed", "semantic", "lexical"]


def test_empty_fusion_short_circuits_before_generation() -> None:
    parts = EngineParts()

    def empty_hybrid_fuser(
        semantic_results: tuple[VectorSearchResult, ...],
        lexical_results: tuple[LexicalSearchResult, ...],
        top_k: int,
        rrf_k: int,
    ) -> tuple[HybridSearchResult, ...]:
        parts.call_log.append("hybrid")
        return ()

    parts.hybrid_fuser = empty_hybrid_fuser  # type: ignore[method-assign]

    with pytest.raises(NoRelevantEvidenceError):
        parts.engine().answer(QUESTION)

    assert parts.call_log == ["embed", "semantic", "lexical", "hybrid"]


def test_empty_reranking_short_circuits_before_generation() -> None:
    parts = EngineParts()

    def empty_reranking_stage(
        question: str,
        candidates: tuple[HybridSearchResult, ...],
        provider: RerankerProvider,
        top_k: int,
    ) -> RerankedSearchResponse:
        parts.call_log.append("reranker")
        return RerankedSearchResponse(question=question, results=())

    parts.reranking_stage = empty_reranking_stage  # type: ignore[method-assign]

    with pytest.raises(NoRelevantEvidenceError):
        parts.engine().answer(QUESTION)

    assert parts.call_log == ["embed", "semantic", "lexical", "hybrid", "reranker"]


def test_empty_evidence_short_circuits_before_generation() -> None:
    parts = EngineParts()

    def empty_evidence_builder(
        candidates: tuple[RerankedSearchResult, ...],
        config: EvidenceContextConfig,
    ) -> EvidenceContext:
        parts.call_log.append("evidence")
        return _empty_evidence_builder(candidates, config)

    parts.evidence_builder = empty_evidence_builder  # type: ignore[method-assign]

    with pytest.raises(NoRelevantEvidenceError):
        parts.engine().answer(QUESTION)

    assert parts.call_log == [
        "embed",
        "semantic",
        "lexical",
        "hybrid",
        "reranker",
        "evidence",
    ]


@pytest.mark.parametrize(
    ("stage", "expected_log"),
    [
        ("embed", ["embed"]),
        ("semantic", ["embed", "semantic"]),
        ("lexical", ["embed", "semantic", "lexical"]),
        ("hybrid", ["embed", "semantic", "lexical", "hybrid"]),
        ("reranker", ["embed", "semantic", "lexical", "hybrid", "reranker"]),
        (
            "evidence",
            ["embed", "semantic", "lexical", "hybrid", "reranker", "evidence"],
        ),
        (
            "prompt",
            [
                "embed",
                "semantic",
                "lexical",
                "hybrid",
                "reranker",
                "evidence",
                "prompt",
            ],
        ),
        (
            "generator",
            [
                "embed",
                "semantic",
                "lexical",
                "hybrid",
                "reranker",
                "evidence",
                "prompt",
                "generator",
            ],
        ),
        (
            "citations",
            [
                "embed",
                "semantic",
                "lexical",
                "hybrid",
                "reranker",
                "evidence",
                "prompt",
                "generator",
                "citations",
            ],
        ),
    ],
)
def test_stage_failures_are_safe_and_stop_later_calls(
    stage: str,
    expected_log: list[str],
) -> None:
    parts = EngineParts(fail_at=stage)

    with pytest.raises(QueryExecutionError) as exc_info:
        parts.engine().answer(QUESTION)

    assert parts.call_log == expected_log
    assert "raw" not in str(exc_info.value)


def test_input_objects_are_not_mutated_on_failure() -> None:
    parts = EngineParts(fail_at="generator")
    semantic_before = parts.semantic.results
    lexical_before = parts.lexical.results

    with pytest.raises(QueryExecutionError):
        parts.engine().answer(QUESTION)

    assert parts.semantic.results == semantic_before
    assert parts.lexical.results == lexical_before


def test_repeated_runs_with_deterministic_collaborators_are_equal() -> None:
    first = EngineParts().engine().answer(QUESTION)
    second = EngineParts().engine().answer(QUESTION)

    assert first == second


def _empty_hybrid_fuser(
    semantic_results: tuple[VectorSearchResult, ...],
    lexical_results: tuple[LexicalSearchResult, ...],
    top_k: int,
    rrf_k: int,
) -> tuple[HybridSearchResult, ...]:
    return ()


def _empty_reranking_stage(
    question: str,
    candidates: tuple[HybridSearchResult, ...],
    provider: RerankerProvider,
    top_k: int,
) -> RerankedSearchResponse:
    return RerankedSearchResponse(question=question, results=())


def _empty_evidence_builder(
    candidates: tuple[RerankedSearchResult, ...],
    config: EvidenceContextConfig,
) -> EvidenceContext:
    evidence = object.__new__(EvidenceContext)
    object.__setattr__(evidence, "items", ())
    object.__setattr__(evidence, "rendered_text", "")
    object.__setattr__(evidence, "total_characters", 0)
    object.__setattr__(evidence, "truncated", False)
    return evidence


def _semantic_results() -> tuple[VectorSearchResult, ...]:
    first = _chunk_one()
    second = _chunk_two()
    return (
        VectorSearchResult(
            indexed=IndexedVector(
                chunk=first,
                vector=EmbeddingVector(item_id=first.chunk_id, values=(0.25, 0.75)),
            ),
            score=0.9,
            rank=1,
        ),
        VectorSearchResult(
            indexed=IndexedVector(
                chunk=second,
                vector=EmbeddingVector(item_id=second.chunk_id, values=(0.1, 0.2)),
            ),
            score=0.8,
            rank=2,
        ),
    )


def _lexical_results() -> tuple[LexicalSearchResult, ...]:
    return (
        LexicalSearchResult(chunk=_chunk_one(), score=3.0, rank=1),
        LexicalSearchResult(chunk=_chunk_two(), score=2.0, rank=2),
    )


def _hybrid_results() -> tuple[HybridSearchResult, ...]:
    return (
        HybridSearchResult(
            chunk=_chunk_one(),
            fused_score=0.4,
            rank=1,
            contributions=(RetrievalContribution("semantic", 1, 0.9),),
        ),
        HybridSearchResult(
            chunk=_chunk_two(),
            fused_score=0.3,
            rank=2,
            contributions=(RetrievalContribution("lexical", 2, 2.0),),
        ),
    )


def _chunk_one() -> DocumentChunk:
    return DocumentChunk(
        chunk_id=CHUNK_ID_1,
        document_id=DOCUMENT_ID_1,
        source=DocumentSource(
            filename="refund-policy.pdf",
            media_type="application/pdf",
            size_bytes=128,
        ),
        page_number=2,
        chunk_index=0,
        text="Refund requests must be submitted within 14 days.",
    )


def _chunk_two() -> DocumentChunk:
    return DocumentChunk(
        chunk_id=CHUNK_ID_2,
        document_id=DOCUMENT_ID_2,
        source=DocumentSource(
            filename="shipping-policy.pdf",
            media_type="application/pdf",
            size_bytes=256,
        ),
        page_number=5,
        chunk_index=1,
        text="Shipping claims require the original receipt.",
    )


def test_successful_observed_query_records_runtime_trace() -> None:
    recorder = InMemoryMetricsRecorder()
    parts = EngineParts()
    clock = FakeMonotonicClock(tuple(float(value) for value in range(20)))

    result = parts.engine(
        metrics_recorder=recorder,
        monotonic_clock=clock,
        utc_clock=FakeUtcClock(),
    ).answer(QUESTION)

    assert result.grounded_answer.answer_text == ANSWER
    trace = recorder.snapshot()[0]
    assert trace.request_id == UUID("00000000-0000-0000-0000-000000000901")
    assert trace.operation == "askme.query"
    assert trace.started_at == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert trace.duration_ms == 21000.0
    assert trace.success is True
    assert trace.error_type is None
    assert [stage.name for stage in trace.stages] == [
        "validation",
        "query_embedding",
        "semantic_retrieval",
        "lexical_retrieval",
        "hybrid_fusion",
        "reranking",
        "evidence_construction",
        "prompt_construction",
        "generation",
        "citation_validation",
    ]
    assert [stage.duration_ms for stage in trace.stages] == [1000.0] * 10
    assert all(stage.success for stage in trace.stages)
    observation = trace.observation
    assert observation is not None
    assert observation.semantic_result_count == 2
    assert observation.lexical_result_count == 2
    assert observation.fused_result_count == 2
    assert observation.reranked_result_count == 2
    assert observation.evidence_count == 2
    assert observation.citation_count == 1
    assert observation.citations_valid is True
    assert observation.citation_precision == 1.0
    assert observation.citation_recall == 1.0
    assert observation.provider_model == "offline-model"
    assert observation.finish_reason == "stop"
    assert observation.failure_category is None


def test_successful_observed_query_records_operational_metrics() -> None:
    trace_recorder = InMemoryMetricsRecorder()
    operational_metrics = InMemoryOperationalMetricsRecorder()
    parts = EngineParts()
    clock = FakeMonotonicClock(tuple(float(value) for value in range(20)))

    parts.engine(
        metrics_recorder=trace_recorder,
        operational_metrics=operational_metrics,
        monotonic_clock=clock,
        utc_clock=FakeUtcClock(),
    ).answer(QUESTION)

    snapshot = operational_metrics.snapshot().as_dict()
    counters = snapshot["counters"]
    durations = snapshot["durations"]
    assert {
        (item["name"], tuple(sorted(item["labels"].items()))): item["value"]
        for item in counters
    } == {
        ("retrieval_candidate_total", (("stage", "bm25"),)): 2,
        ("retrieval_candidate_total", (("stage", "final"),)): 2,
        ("retrieval_candidate_total", (("stage", "fused"),)): 2,
        ("retrieval_candidate_total", (("stage", "vector"),)): 2,
        ("retrieval_query_total", (("success", "True"),)): 1,
    }
    assert durations == [
        {
            "name": "retrieval_duration_ms",
            "labels": {"success": "True"},
            "count": 1,
            "total_ms": 21000.0,
            "max_ms": 21000.0,
        }
    ]


def test_observed_no_evidence_records_empty_operational_metric() -> None:
    trace_recorder = InMemoryMetricsRecorder()
    operational_metrics = InMemoryOperationalMetricsRecorder()
    parts = EngineParts()
    parts.semantic.results = ()
    parts.lexical.results = ()
    clock = FakeMonotonicClock(tuple(float(value) for value in range(9)))

    with pytest.raises(NoRelevantEvidenceError):
        parts.engine(
            metrics_recorder=trace_recorder,
            operational_metrics=operational_metrics,
            monotonic_clock=clock,
            utc_clock=FakeUtcClock(),
        ).answer(QUESTION)

    snapshot = operational_metrics.snapshot().as_dict()
    counters = {
        (item["name"], tuple(sorted(item["labels"].items()))): item["value"]
        for item in snapshot["counters"]
    }
    assert counters == {
        ("retrieval_empty_result_total", ()): 1,
        ("retrieval_query_total", (("success", "False"),)): 1,
    }


def test_observed_no_evidence_failure_records_safe_trace_and_stops_generation() -> None:
    recorder = InMemoryMetricsRecorder()
    parts = EngineParts()
    parts.semantic.results = ()
    parts.lexical.results = ()
    clock = FakeMonotonicClock(tuple(float(value) for value in range(9)))

    with pytest.raises(NoRelevantEvidenceError):
        parts.engine(
            metrics_recorder=recorder,
            monotonic_clock=clock,
            utc_clock=FakeUtcClock(),
        ).answer(QUESTION)

    assert parts.call_log == ["embed", "semantic", "lexical"]
    trace = recorder.snapshot()[0]
    assert trace.success is False
    assert trace.error_type == "NoRelevantEvidenceError"
    assert [stage.name for stage in trace.stages] == [
        "validation",
        "query_embedding",
        "semantic_retrieval",
        "lexical_retrieval",
    ]
    assert all(stage.success for stage in trace.stages)
    observation = trace.observation
    assert observation is not None
    assert observation.semantic_result_count == 0
    assert observation.lexical_result_count == 0
    assert observation.fused_result_count is None
    assert observation.reranked_result_count is None
    assert observation.evidence_count is None
    assert observation.citation_count is None
    assert observation.provider_model is None
    assert observation.finish_reason is None
    assert observation.failure_category == "NoRelevantEvidenceError"


def test_observed_stage_failure_records_failed_stage_without_raw_details() -> None:
    recorder = InMemoryMetricsRecorder()
    parts = EngineParts(fail_at="generator")
    clock = FakeMonotonicClock(tuple(float(value) for value in range(18)))

    with pytest.raises(QueryExecutionError) as exc_info:
        parts.engine(
            metrics_recorder=recorder,
            monotonic_clock=clock,
            utc_clock=FakeUtcClock(),
        ).answer(QUESTION)

    assert "raw generation details" not in str(exc_info.value)
    trace = recorder.snapshot()[0]
    assert trace.success is False
    assert trace.error_type == "QueryExecutionError"
    assert trace.stages[-1].name == "generation"
    assert trace.stages[-1].success is False
    assert trace.stages[-1].error_type == "QueryExecutionError"
    observation = trace.observation
    assert observation is not None
    assert observation.semantic_result_count == 2
    assert observation.lexical_result_count == 2
    assert observation.fused_result_count == 2
    assert observation.reranked_result_count == 2
    assert observation.evidence_count == 2
    assert observation.citation_count is None
    assert observation.failure_category == "QueryExecutionError"
    trace_text = repr(trace)
    assert "raw generation details" not in trace_text
    assert ANSWER not in trace_text
    assert "Refund requests must be submitted within 14 days." not in trace_text


def test_observed_blank_question_records_validation_failure() -> None:
    recorder = InMemoryMetricsRecorder()
    clock = FakeMonotonicClock((0.0, 1.0, 2.0))

    with pytest.raises(QueryCompositionError):
        EngineParts().engine(
            metrics_recorder=recorder,
            monotonic_clock=clock,
            utc_clock=FakeUtcClock(),
        ).answer("   ")

    trace = recorder.snapshot()[0]
    assert trace.success is False
    assert trace.error_type == "QueryCompositionError"
    assert [stage.name for stage in trace.stages] == ["validation"]
    assert trace.stages[0].success is False
    assert trace.observation is not None
    assert trace.observation.failure_category == "QueryCompositionError"


class FakeMonotonicClock:
    def __init__(self, values: tuple[float, ...]) -> None:
        self._values = values
        self._index = 0

    def now(self) -> float:
        if self._index >= len(self._values):
            value = self._values[-1] + float(self._index - len(self._values) + 1)
        else:
            value = self._values[self._index]
        self._index += 1
        return value


class FakeUtcClock:
    def now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=timezone.utc)
