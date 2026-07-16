"""Local Sentence Transformers embedding provider."""

from collections.abc import Callable, Iterable
from importlib import import_module
from typing import Any, cast

from loreforge.embeddings.models import (
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingVector,
)

DEFAULT_LOCAL_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class LocalEmbeddingError(RuntimeError):
    """Raised when the local embedding model cannot load or run safely."""


class LocalSentenceTransformerProvider:
    """Embedding provider backed by a lazily loaded local Sentence Transformer."""

    def __init__(
        self,
        model_name: str = DEFAULT_LOCAL_MODEL_NAME,
        batch_size: int = 32,
        *,
        _model_factory: Callable[[str], Any] | None = None,
    ) -> None:
        if not model_name.strip():
            msg = "model_name must not be empty"
            raise ValueError(msg)

        if batch_size <= 0:
            msg = "batch_size must be greater than zero"
            raise ValueError(msg)

        self.model_name = model_name
        self.batch_size = batch_size
        self._model_factory = _model_factory or _load_sentence_transformer_model
        self._model: Any | None = None

    def embed(
        self,
        requests: tuple[EmbeddingRequest, ...],
    ) -> EmbeddingResult:
        """Embed ordered text requests using the configured local model."""
        if not requests:
            msg = "requests must contain at least one request"
            raise ValueError(msg)

        model = self._get_model()
        texts = tuple(request.text for request in requests)

        try:
            raw_embeddings = self._encode_documents(model, texts)
        except Exception as error:
            msg = "local embedding inference failed"
            raise LocalEmbeddingError(msg) from error

        vectors = tuple(
            EmbeddingVector(
                item_id=request.item_id,
                values=_to_float_tuple(raw_vector),
            )
            for request, raw_vector in zip(requests, raw_embeddings, strict=True)
        )

        dimensions = len(vectors[0].values)
        return EmbeddingResult(
            model=self.model_name,
            dimensions=dimensions,
            vectors=vectors,
        )

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                self._model = self._model_factory(self.model_name)
            except Exception as error:
                msg = "local embedding model could not be loaded"
                raise LocalEmbeddingError(msg) from error

        return self._model

    def _encode_documents(
        self,
        model: Any,
        texts: tuple[str, ...],
    ) -> Iterable[Iterable[object]]:
        if hasattr(model, "encode_document"):
            raw_embeddings = model.encode_document(texts, batch_size=self.batch_size)
            return cast(Iterable[Iterable[Any]], raw_embeddings)

        raw_embeddings = model.encode(texts, batch_size=self.batch_size)
        return cast(Iterable[Iterable[Any]], raw_embeddings)


def _to_float_tuple(values: Iterable[Any]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)


def _load_sentence_transformer_model(model_name: str) -> Any:
    sentence_transformers = import_module("sentence_transformers")
    sentence_transformer = sentence_transformers.SentenceTransformer

    return sentence_transformer(model_name)
