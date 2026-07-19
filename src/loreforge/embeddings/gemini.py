"""Gemini embedding provider backed by the Google Gen AI SDK."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from importlib import import_module
from math import isfinite
from typing import Any, Protocol, cast
from uuid import uuid4

from loreforge.embeddings.models import (
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingVector,
)

_DOCUMENT_TASK_TYPE = "RETRIEVAL_DOCUMENT"
_QUERY_TASK_TYPE = "RETRIEVAL_QUERY"


class GeminiEmbeddingError(RuntimeError):
    """Raised when Gemini embeddings cannot complete safely."""


@dataclass(frozen=True, slots=True)
class GeminiEmbeddingConfig:
    """Configuration for Gemini document and query embeddings."""

    api_key: str = field(repr=False)
    model: str
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            msg = "api_key must not be empty"
            raise ValueError(msg)
        if not self.model.strip():
            msg = "model must not be empty"
            raise ValueError(msg)
        if type(self.timeout_seconds) is not float:
            msg = "timeout_seconds must be a float"
            raise ValueError(msg)
        if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0.0:
            msg = "timeout_seconds must be finite and greater than zero"
            raise ValueError(msg)


class _GeminiModelsClient(Protocol):
    def embed_content(
        self,
        *,
        model: str,
        contents: list[str],
        config: Any,
    ) -> Any:
        """Embed ordered contents with Gemini."""
        ...


class _GeminiClient(Protocol):
    models: _GeminiModelsClient


def create_gemini_client(*, api_key: str, timeout_seconds: float) -> _GeminiClient:
    """Create a Google Gen AI SDK client for Gemini Developer API calls."""
    genai = import_module("google.genai")
    types = import_module("google.genai.types")
    timeout_milliseconds = _timeout_milliseconds(timeout_seconds)
    return cast(
        _GeminiClient,
        genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_milliseconds),
        ),
    )


class GeminiEmbeddingProvider:
    """Embedding provider that calls Gemini through the Google Gen AI SDK."""

    def __init__(
        self,
        config: GeminiEmbeddingConfig,
        client: _GeminiClient | None = None,
    ) -> None:
        self._config = config
        self._client = client

    def embed(self, requests: tuple[EmbeddingRequest, ...]) -> EmbeddingResult:
        """Embed ordered document text requests."""
        return self.embed_documents(requests)

    def embed_documents(
        self,
        requests: tuple[EmbeddingRequest, ...],
    ) -> EmbeddingResult:
        """Embed ordered document text requests with Gemini retrieval-document mode."""
        return self._embed_requests(requests, task_type=_DOCUMENT_TASK_TYPE)

    def embed_query(self, question: str) -> EmbeddingVector:
        """Embed one user query with Gemini retrieval-query mode."""
        result = self._embed_requests(
            (EmbeddingRequest(item_id=uuid4(), text=question),),
            task_type=_QUERY_TASK_TYPE,
        )
        return result.vectors[0]

    def _embed_requests(
        self,
        requests: tuple[EmbeddingRequest, ...],
        *,
        task_type: str,
    ) -> EmbeddingResult:
        if not requests:
            msg = "requests must contain at least one request"
            raise ValueError(msg)

        try:
            response = self._get_client().models.embed_content(
                model=self._config.model,
                contents=[request.text for request in requests],
                config=_embedding_config(
                    task_type=task_type,
                    timeout_seconds=self._config.timeout_seconds,
                ),
            )
        except GeminiEmbeddingError:
            raise
        except Exception as error:
            msg = "gemini embedding request failed"
            raise GeminiEmbeddingError(msg) from error

        vectors = _embedding_vectors_from_response(response, requests)
        dimensions = len(vectors[0].values)
        return EmbeddingResult(
            model=self._config.model,
            dimensions=dimensions,
            vectors=vectors,
        )

    def _get_client(self) -> _GeminiClient:
        if self._client is None:
            self._client = create_gemini_client(
                api_key=self._config.api_key,
                timeout_seconds=self._config.timeout_seconds,
            )
        return self._client


def _embedding_config(*, task_type: str, timeout_seconds: float) -> Any:
    types = import_module("google.genai.types")
    return types.EmbedContentConfig(
        task_type=task_type,
        http_options=types.HttpOptions(timeout=_timeout_milliseconds(timeout_seconds)),
    )


def _embedding_vectors_from_response(
    response: Any,
    requests: tuple[EmbeddingRequest, ...],
) -> tuple[EmbeddingVector, ...]:
    raw_embeddings = _field(response, "embeddings")
    if not isinstance(raw_embeddings, Sequence) or isinstance(raw_embeddings, str):
        msg = "gemini embedding response must contain embeddings"
        raise GeminiEmbeddingError(msg)
    if len(raw_embeddings) != len(requests):
        msg = "gemini embedding response count did not match request count"
        raise GeminiEmbeddingError(msg)

    try:
        return tuple(
            EmbeddingVector(
                item_id=request.item_id,
                values=_float_tuple(_field(raw_embedding, "values")),
            )
            for request, raw_embedding in zip(requests, raw_embeddings, strict=True)
        )
    except (TypeError, ValueError) as error:
        msg = "gemini embedding response contained malformed vectors"
        raise GeminiEmbeddingError(msg) from error


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _float_tuple(values: Any) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)):
        msg = "embedding values must be numeric"
        raise TypeError(msg)
    return tuple(float(value) for value in cast(Iterable[Any], values))


def _timeout_milliseconds(timeout_seconds: float) -> int:
    return max(1, int(timeout_seconds * 1000))


__all__ = [
    "GeminiEmbeddingConfig",
    "GeminiEmbeddingError",
    "GeminiEmbeddingProvider",
    "create_gemini_client",
]
