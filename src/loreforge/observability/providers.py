"""Provider observation adapters."""

from time import perf_counter

from loreforge.embeddings import (
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingVector,
    QueryEmbeddingProvider,
)
from loreforge.embeddings.provider import EmbeddingProvider
from loreforge.generation.models import GenerationRequest, GenerationResponse
from loreforge.generation.provider import LLMProvider
from loreforge.observability.operational import OperationalMetricsRecorder


class ObservedDocumentEmbeddingProvider:
    """Record safe operational metrics around document embedding calls."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        *,
        metrics: OperationalMetricsRecorder,
        provider_name: str,
        model: str,
    ) -> None:
        self._provider = provider
        self._metrics = metrics
        self._labels = {"provider": provider_name, "model": model}

    def embed(
        self,
        requests: tuple[EmbeddingRequest, ...],
    ) -> EmbeddingResult:
        start = perf_counter()
        try:
            result = self._provider.embed(requests)
        except Exception:
            self._record("document_embedding", start, success=False)
            raise
        self._record("document_embedding", start, success=True)
        return result

    def _record(self, operation: str, start: float, *, success: bool) -> None:
        labels = {**self._labels, "operation": operation, "success": str(success)}
        self._metrics.increment("provider_operation_total", labels=labels)
        self._metrics.observe_duration(
            "provider_operation_duration_ms",
            float((perf_counter() - start) * 1000.0),
            labels=labels,
        )


class ObservedQueryEmbeddingProvider:
    """Record safe operational metrics around query embedding provider calls."""

    def __init__(
        self,
        provider: QueryEmbeddingProvider,
        *,
        metrics: OperationalMetricsRecorder,
        provider_name: str,
        model: str,
    ) -> None:
        self._provider = provider
        self._metrics = metrics
        self._labels = {"provider": provider_name, "model": model}

    def embed_documents(
        self,
        requests: tuple[EmbeddingRequest, ...],
    ) -> EmbeddingResult:
        start = perf_counter()
        try:
            result = self._provider.embed_documents(requests)
        except Exception:
            self._record("document_embedding", start, success=False)
            raise
        self._record("document_embedding", start, success=True)
        return result

    def embed_query(self, question: str) -> EmbeddingVector:
        start = perf_counter()
        try:
            result = self._provider.embed_query(question)
        except Exception:
            self._record("query_embedding", start, success=False)
            raise
        self._record("query_embedding", start, success=True)
        return result

    def _record(self, operation: str, start: float, *, success: bool) -> None:
        labels = {**self._labels, "operation": operation, "success": str(success)}
        self._metrics.increment("provider_operation_total", labels=labels)
        self._metrics.observe_duration(
            "provider_operation_duration_ms",
            float((perf_counter() - start) * 1000.0),
            labels=labels,
        )


class ObservedLLMProvider:
    """Record safe operational metrics around LLM provider calls."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        metrics: OperationalMetricsRecorder,
        provider_name: str,
        model: str,
    ) -> None:
        self._provider = provider
        self._metrics = metrics
        self._labels = {"provider": provider_name, "model": model}

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        start = perf_counter()
        try:
            response = self._provider.generate(request)
        except Exception:
            self._record(start, success=False)
            raise
        self._record(start, success=True)
        return response

    def _record(self, start: float, *, success: bool) -> None:
        labels = {**self._labels, "operation": "generation", "success": str(success)}
        self._metrics.increment("provider_operation_total", labels=labels)
        self._metrics.observe_duration(
            "provider_operation_duration_ms",
            float((perf_counter() - start) * 1000.0),
            labels=labels,
        )
