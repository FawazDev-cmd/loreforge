"""Local Sentence Transformers cross-encoder reranker."""

import logging
from collections.abc import Callable, Iterable
from importlib import import_module
from time import perf_counter
from typing import Any, cast

from loreforge.reranking.models import RerankingRequest, RerankingScore

_logger = logging.getLogger(__name__)

DEFAULT_CROSS_ENCODER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L6-v2"


class LocalRerankingError(RuntimeError):
    """Raised when the local cross-encoder cannot load or score safely."""


class LocalCrossEncoderReranker:
    """Reranker backed by a lazily loaded local Sentence Transformers CrossEncoder."""

    def __init__(
        self,
        model_name: str = DEFAULT_CROSS_ENCODER_MODEL_NAME,
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
        self._model_factory = _model_factory or _load_cross_encoder_model
        self._model: Any | None = None

    def score(
        self,
        requests: tuple[RerankingRequest, ...],
    ) -> tuple[RerankingScore, ...]:
        """Score ordered query-passage requests with the local cross-encoder."""
        if not requests:
            msg = "requests must contain at least one request"
            raise ValueError(msg)

        model_preloaded = self._model is not None
        model = self._get_model()
        pairs = tuple((request.query, request.passage) for request in requests)
        _logger.warning(
            "askme.latency reranker.predict.request model=%s request_count=%d "
            "batch_size=%d model_preloaded=%s total_passage_chars=%d",
            self.model_name,
            len(requests),
            self.batch_size,
            model_preloaded,
            sum(len(request.passage) for request in requests),
        )
        started_at = perf_counter()

        try:
            raw_scores = tuple(
                _as_iterable(model.predict(pairs, batch_size=self.batch_size))
            )
        except Exception as error:
            msg = "local reranking inference failed"
            raise LocalRerankingError(msg) from error

        _logger.warning(
            "askme.latency reranker.predict.response duration_ms=%.2f score_count=%d",
            (perf_counter() - started_at) * 1000.0,
            len(raw_scores),
        )

        if len(raw_scores) != len(requests):
            msg = "local reranking model returned an unexpected number of scores"
            raise LocalRerankingError(msg)

        try:
            return tuple(
                RerankingScore(item_id=request.item_id, score=_to_float(raw_score))
                for request, raw_score in zip(requests, raw_scores, strict=True)
            )
        except (TypeError, ValueError) as error:
            msg = "local reranking model returned malformed scores"
            raise LocalRerankingError(msg) from error

    def _get_model(self) -> Any:
        if self._model is None:
            _logger.warning(
                "askme.latency reranker.model_load.request model=%s",
                self.model_name,
            )
            started_at = perf_counter()
            try:
                self._model = self._model_factory(self.model_name)
            except Exception as error:
                _logger.warning(
                    "askme.latency reranker.model_load.error duration_ms=%.2f",
                    (perf_counter() - started_at) * 1000.0,
                )
                msg = "local reranking model could not be loaded"
                raise LocalRerankingError(msg) from error
            _logger.warning(
                "askme.latency reranker.model_load.response duration_ms=%.2f",
                (perf_counter() - started_at) * 1000.0,
            )

        return self._model

    def warm_up(self) -> None:
        """Load the local cross-encoder model before the first scoring request."""
        self._get_model()


def _to_float(value: Any) -> float:
    return float(value)


def _as_iterable(values: Any) -> Iterable[Any]:
    if isinstance(values, (str, bytes)):
        return (values,)

    try:
        return iter(cast(Iterable[Any], values))
    except TypeError:
        return (values,)


def _load_cross_encoder_model(model_name: str) -> Any:
    sentence_transformers = import_module("sentence_transformers")
    cross_encoder = sentence_transformers.CrossEncoder

    return cross_encoder(model_name)
