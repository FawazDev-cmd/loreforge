"""Production grounded-query composition engine."""

from collections.abc import Callable
from uuid import UUID, uuid4

from loreforge.embeddings import EmbeddingVector, QueryEmbeddingProvider
from loreforge.evaluation import evaluate_citations
from loreforge.generation.answer_models import GroundedAnswer
from loreforge.generation.citations import validate_grounded_answer
from loreforge.generation.evidence import (
    EvidenceContext,
    EvidenceContextConfig,
)
from loreforge.generation.evidence import (
    build_evidence_context as default_evidence_builder,
)
from loreforge.generation.models import generation_request_from_prompt
from loreforge.generation.orchestration import source_references_from_evidence
from loreforge.generation.prompting import PromptPackage, build_grounded_prompt
from loreforge.generation.provider import LLMProvider
from loreforge.generation.validation_models import ValidatedGroundedAnswer
from loreforge.observability import (
    MetricsRecorder,
    MonotonicClock,
    OperationalMetricsRecorder,
    RequestTracer,
    RuntimeQueryObservation,
    UtcClock,
)
from loreforge.query.errors import (
    NoRelevantEvidenceError,
    QueryCompositionError,
    QueryExecutionError,
)
from loreforge.reranking import (
    RerankedSearchResponse,
    RerankedSearchResult,
    RerankerProvider,
)
from loreforge.reranking.pipeline import rerank_hybrid_results
from loreforge.retrieval import (
    HybridSearchResult,
    LexicalSearchRequest,
    LexicalSearchResponse,
    LexicalSearchResult,
)
from loreforge.retrieval.bm25 import InMemoryBM25Index
from loreforge.retrieval.hybrid import reciprocal_rank_fusion
from loreforge.vector_index import InMemoryVectorIndex, VectorSearchResult

_QUERY_EXECUTION_ERROR = "query execution failed"
_NO_RELEVANT_EVIDENCE = "no relevant evidence was found"
_OBSERVED_OPERATION = "askme.query"

HybridFuser = Callable[
    [tuple[VectorSearchResult, ...], tuple[LexicalSearchResult, ...], int, int],
    tuple[HybridSearchResult, ...],
]
EvidenceBuilder = Callable[
    [tuple[RerankedSearchResult, ...], EvidenceContextConfig], EvidenceContext
]
PromptBuilder = Callable[[str, EvidenceContext], PromptPackage]
CitationEnforcer = Callable[[GroundedAnswer], ValidatedGroundedAnswer]
RerankingStage = Callable[
    [str, tuple[HybridSearchResult, ...], RerankerProvider, int],
    RerankedSearchResponse,
]


class ProductionGroundedQueryEngine:
    """Compose existing LoreForge RAG components into one grounded query flow."""

    def __init__(
        self,
        *,
        query_embedder: QueryEmbeddingProvider,
        semantic_retriever: InMemoryVectorIndex,
        lexical_retriever: InMemoryBM25Index,
        reranker: RerankerProvider,
        answer_generator: LLMProvider,
        hybrid_fuser: HybridFuser | None = None,
        evidence_builder: EvidenceBuilder | None = None,
        prompt_builder: PromptBuilder | None = None,
        citation_enforcer: CitationEnforcer = validate_grounded_answer,
        reranking_stage: RerankingStage | None = None,
        metrics_recorder: MetricsRecorder | None = None,
        operational_metrics: OperationalMetricsRecorder | None = None,
        trace_id_factory: Callable[[], UUID] = uuid4,
        monotonic_clock: MonotonicClock | None = None,
        utc_clock: UtcClock | None = None,
        semantic_top_k: int = 10,
        lexical_top_k: int = 10,
        hybrid_top_k: int = 10,
        rerank_top_k: int = 5,
        rrf_k: int = 60,
        evidence_max_characters: int = 12000,
        max_output_tokens: int = 800,
        temperature: float = 0.0,
    ) -> None:
        self._query_embedder = query_embedder
        self._semantic_retriever = semantic_retriever
        self._lexical_retriever = lexical_retriever
        self._reranker = reranker
        self._answer_generator = answer_generator
        self._hybrid_fuser = hybrid_fuser or _default_hybrid_fuser
        self._evidence_builder = evidence_builder or _default_evidence_builder
        self._prompt_builder = prompt_builder or _default_prompt_builder
        self._citation_enforcer = citation_enforcer
        self._reranking_stage = reranking_stage or _default_reranking_stage
        self._metrics_recorder = metrics_recorder
        self._operational_metrics = operational_metrics
        self._trace_id_factory = trace_id_factory
        self._monotonic_clock = monotonic_clock
        self._utc_clock = utc_clock
        self._semantic_top_k = semantic_top_k
        self._lexical_top_k = lexical_top_k
        self._hybrid_top_k = hybrid_top_k
        self._rerank_top_k = rerank_top_k
        self._rrf_k = rrf_k
        self._evidence_max_characters = evidence_max_characters
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature

    def answer(self, question: str) -> ValidatedGroundedAnswer:
        """Return a citation-validated grounded answer for a question."""
        if self._metrics_recorder is None:
            return self._answer_unobserved(question)
        return self._answer_observed(question)

    def _answer_unobserved(self, question: str) -> ValidatedGroundedAnswer:
        self._validate_question(question)
        query_vector = self._embed_query(question)
        semantic_results = self._semantic_search(query_vector)
        lexical_response = self._lexical_search(question)
        if not semantic_results and not lexical_response.results:
            raise NoRelevantEvidenceError(_NO_RELEVANT_EVIDENCE)

        hybrid_results = self._fuse_results(semantic_results, lexical_response)
        if not hybrid_results:
            raise NoRelevantEvidenceError(_NO_RELEVANT_EVIDENCE)

        reranked = self._rerank(question, hybrid_results)
        if not reranked.results:
            raise NoRelevantEvidenceError(_NO_RELEVANT_EVIDENCE)

        evidence = self._build_evidence(reranked)
        if not evidence.items:
            raise NoRelevantEvidenceError(_NO_RELEVANT_EVIDENCE)

        prompt = self._build_prompt(question, evidence)
        grounded_answer = self._generate_answer(question, evidence, prompt)
        return self._enforce_citations(grounded_answer)

    def _answer_observed(self, question: str) -> ValidatedGroundedAnswer:
        if self._metrics_recorder is None:
            return self._answer_unobserved(question)

        tracer = RequestTracer(
            operation=_OBSERVED_OPERATION,
            recorder=self._metrics_recorder,
            request_id=self._trace_id_factory(),
            monotonic_clock=self._monotonic_clock,
            utc_clock=self._utc_clock,
        )
        observation = _RuntimeObservationBuilder()

        try:
            with tracer.stage("validation"):
                self._validate_question(question)
            with tracer.stage("query_embedding"):
                query_vector = self._embed_query(question)
            with tracer.stage("semantic_retrieval"):
                semantic_results = self._semantic_search(query_vector)
            observation.semantic_result_count = len(semantic_results)
            with tracer.stage("lexical_retrieval"):
                lexical_response = self._lexical_search(question)
            observation.lexical_result_count = len(lexical_response.results)
            if not semantic_results and not lexical_response.results:
                raise NoRelevantEvidenceError(_NO_RELEVANT_EVIDENCE)

            with tracer.stage("hybrid_fusion"):
                hybrid_results = self._fuse_results(semantic_results, lexical_response)
            observation.fused_result_count = len(hybrid_results)
            if not hybrid_results:
                raise NoRelevantEvidenceError(_NO_RELEVANT_EVIDENCE)

            with tracer.stage("reranking"):
                reranked = self._rerank(question, hybrid_results)
            observation.reranked_result_count = len(reranked.results)
            if not reranked.results:
                raise NoRelevantEvidenceError(_NO_RELEVANT_EVIDENCE)

            with tracer.stage("evidence_construction"):
                evidence = self._build_evidence(reranked)
            observation.evidence_count = len(evidence.items)
            if not evidence.items:
                raise NoRelevantEvidenceError(_NO_RELEVANT_EVIDENCE)

            with tracer.stage("prompt_construction"):
                prompt = self._build_prompt(question, evidence)
            with tracer.stage("generation"):
                grounded_answer = self._generate_answer(question, evidence, prompt)
            observation.provider_model = grounded_answer.provider_model
            observation.finish_reason = grounded_answer.finish_reason
            with tracer.stage("citation_validation"):
                validated_answer = self._enforce_citations(grounded_answer)
            observation.record_citation_evaluation(validated_answer)
        except BaseException as exc:
            self._finish_failure_safely(tracer, exc, observation)
            raise

        self._finish_success_safely(tracer, observation)
        return validated_answer

    def _validate_question(self, question: str) -> None:
        question_object: object = question
        if type(question_object) is not str:
            raise QueryCompositionError("question must be a string")
        if not question.strip():
            raise QueryCompositionError("question must not be empty")

    def _embed_query(self, question: str) -> EmbeddingVector:
        try:
            return self._query_embedder.embed_query(question)
        except QueryCompositionError:
            raise
        except Exception as exc:
            raise QueryExecutionError(_QUERY_EXECUTION_ERROR) from exc

    def _semantic_search(
        self,
        query_vector: EmbeddingVector,
    ) -> tuple[VectorSearchResult, ...]:
        try:
            return self._semantic_retriever.search(
                query_vector=query_vector.values,
                top_k=self._semantic_top_k,
            )
        except QueryCompositionError:
            raise
        except Exception as exc:
            raise QueryExecutionError(_QUERY_EXECUTION_ERROR) from exc

    def _lexical_search(self, question: str) -> LexicalSearchResponse:
        try:
            return self._lexical_retriever.search(
                LexicalSearchRequest(query=question, top_k=self._lexical_top_k)
            )
        except QueryCompositionError:
            raise
        except Exception as exc:
            raise QueryExecutionError(_QUERY_EXECUTION_ERROR) from exc

    def _fuse_results(
        self,
        semantic_results: tuple[VectorSearchResult, ...],
        lexical_response: LexicalSearchResponse,
    ) -> tuple[HybridSearchResult, ...]:
        try:
            return self._hybrid_fuser(
                semantic_results,
                lexical_response.results,
                self._hybrid_top_k,
                self._rrf_k,
            )
        except QueryCompositionError:
            raise
        except Exception as exc:
            raise QueryExecutionError(_QUERY_EXECUTION_ERROR) from exc

    def _rerank(
        self,
        question: str,
        candidates: tuple[HybridSearchResult, ...],
    ) -> RerankedSearchResponse:
        try:
            return self._reranking_stage(
                question,
                candidates,
                self._reranker,
                self._rerank_top_k,
            )
        except QueryCompositionError:
            raise
        except Exception as exc:
            raise QueryExecutionError(_QUERY_EXECUTION_ERROR) from exc

    def _build_evidence(self, reranked: RerankedSearchResponse) -> EvidenceContext:
        try:
            return self._evidence_builder(
                reranked.results,
                EvidenceContextConfig(max_characters=self._evidence_max_characters),
            )
        except QueryCompositionError:
            raise
        except Exception as exc:
            raise QueryExecutionError(_QUERY_EXECUTION_ERROR) from exc

    def _build_prompt(self, question: str, evidence: EvidenceContext) -> PromptPackage:
        try:
            return self._prompt_builder(question, evidence)
        except QueryCompositionError:
            raise
        except Exception as exc:
            raise QueryExecutionError(_QUERY_EXECUTION_ERROR) from exc

    def _generate_answer(
        self,
        question: str,
        evidence: EvidenceContext,
        prompt: PromptPackage,
    ) -> GroundedAnswer:
        try:
            generation_request = generation_request_from_prompt(
                prompt,
                max_output_tokens=self._max_output_tokens,
                temperature=self._temperature,
            )
            generation_response = self._answer_generator.generate(generation_request)
            sources = source_references_from_evidence(evidence)
            if not sources:
                raise NoRelevantEvidenceError(_NO_RELEVANT_EVIDENCE)
            return GroundedAnswer(
                question=question,
                answer_text=generation_response.text,
                sources=sources,
                evidence=evidence,
                provider_model=generation_response.model,
                finish_reason=generation_response.finish_reason,
                citations_validated=False,
            )
        except NoRelevantEvidenceError:
            raise
        except QueryCompositionError:
            raise
        except Exception as exc:
            raise QueryExecutionError(_QUERY_EXECUTION_ERROR) from exc

    def _enforce_citations(self, answer: GroundedAnswer) -> ValidatedGroundedAnswer:
        try:
            return self._citation_enforcer(answer)
        except QueryCompositionError:
            raise
        except Exception as exc:
            raise QueryExecutionError(_QUERY_EXECUTION_ERROR) from exc

    def _record_retrieval_metrics(
        self,
        duration_ms: float,
        observation: RuntimeQueryObservation,
        *,
        success: bool,
    ) -> None:
        if self._operational_metrics is None:
            return
        labels = {"success": str(success)}
        self._operational_metrics.increment("retrieval_query_total", labels=labels)
        self._operational_metrics.observe_duration(
            "retrieval_duration_ms",
            duration_ms,
            labels=labels,
        )
        self._increment_result_count("vector", observation.semantic_result_count)
        self._increment_result_count("bm25", observation.lexical_result_count)
        self._increment_result_count("fused", observation.fused_result_count)
        self._increment_result_count("final", observation.reranked_result_count)
        if observation.evidence_count == 0 or (
            not success and observation.failure_category == "NoRelevantEvidenceError"
        ):
            self._operational_metrics.increment("retrieval_empty_result_total")

    def _increment_result_count(self, stage: str, count: int | None) -> None:
        if self._operational_metrics is None or count is None or count <= 0:
            return
        self._operational_metrics.increment(
            "retrieval_candidate_total",
            labels={"stage": stage},
            amount=count,
        )

    def _finish_success_safely(
        self,
        tracer: RequestTracer,
        observation: "_RuntimeObservationBuilder",
    ) -> None:
        runtime_observation = observation.to_observation()
        try:
            trace = tracer.finish_success(observation=runtime_observation)
        except Exception:
            return
        self._record_retrieval_metrics(
            trace.duration_ms,
            runtime_observation,
            success=True,
        )

    def _finish_failure_safely(
        self,
        tracer: RequestTracer,
        error: BaseException,
        observation: "_RuntimeObservationBuilder",
    ) -> None:
        runtime_observation = observation.to_observation(error)
        try:
            trace = tracer.finish_failure(error, observation=runtime_observation)
        except Exception:
            return
        self._record_retrieval_metrics(
            trace.duration_ms,
            runtime_observation,
            success=False,
        )


class _RuntimeObservationBuilder:
    def __init__(self) -> None:
        self.semantic_result_count: int | None = None
        self.lexical_result_count: int | None = None
        self.fused_result_count: int | None = None
        self.reranked_result_count: int | None = None
        self.evidence_count: int | None = None
        self.citation_count: int | None = None
        self.citations_valid: bool | None = None
        self.citation_precision: float | None = None
        self.citation_recall: float | None = None
        self.provider_model: str | None = None
        self.finish_reason: str | None = None

    def record_citation_evaluation(self, answer: ValidatedGroundedAnswer) -> None:
        precision, recall = evaluate_citations(
            expected_citation_ids=answer.citation_validation.supported_citation_ids,
            observed_citation_ids=answer.citation_validation.citation_ids,
        )
        self.citation_count = len(answer.citation_validation.citation_ids)
        self.citations_valid = answer.citation_validation.is_valid
        self.citation_precision = precision
        self.citation_recall = recall

    def to_observation(
        self,
        error: BaseException | None = None,
    ) -> RuntimeQueryObservation:
        return RuntimeQueryObservation(
            semantic_result_count=self.semantic_result_count,
            lexical_result_count=self.lexical_result_count,
            fused_result_count=self.fused_result_count,
            reranked_result_count=self.reranked_result_count,
            evidence_count=self.evidence_count,
            citation_count=self.citation_count,
            citations_valid=self.citations_valid,
            citation_precision=self.citation_precision,
            citation_recall=self.citation_recall,
            provider_model=self.provider_model,
            finish_reason=self.finish_reason,
            failure_category=None if error is None else type(error).__name__,
        )


def _default_reranking_stage(
    question: str,
    candidates: tuple[HybridSearchResult, ...],
    provider: RerankerProvider,
    top_k: int,
) -> RerankedSearchResponse:
    return rerank_hybrid_results(
        question=question,
        candidates=candidates,
        provider=provider,
        top_k=top_k,
    )


def _default_hybrid_fuser(
    semantic_results: tuple[VectorSearchResult, ...],
    lexical_results: tuple[LexicalSearchResult, ...],
    top_k: int,
    rrf_k: int,
) -> tuple[HybridSearchResult, ...]:
    return reciprocal_rank_fusion(
        semantic_results=semantic_results,
        lexical_results=lexical_results,
        top_k=top_k,
        rrf_k=rrf_k,
    )


def _default_evidence_builder(
    candidates: tuple[RerankedSearchResult, ...],
    config: EvidenceContextConfig,
) -> EvidenceContext:
    return default_evidence_builder(candidates=candidates, config=config)


def _default_prompt_builder(question: str, evidence: EvidenceContext) -> PromptPackage:
    return build_grounded_prompt(question=question, evidence=evidence)
