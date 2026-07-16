from uuid import uuid4

import pytest

from loreforge.reranking import (
    LocalCrossEncoderReranker,
    LocalRerankingError,
    RerankerProvider,
    RerankingRequest,
)


class FloatLike:
    def __init__(self, value: float) -> None:
        self.value = value

    def __float__(self) -> float:
        return self.value


class FakeCrossEncoder:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[tuple[str, str], ...], int]] = []

    def predict(
        self,
        pairs: tuple[tuple[str, str], ...],
        *,
        batch_size: int,
    ) -> tuple[FloatLike, ...]:
        self.calls.append((pairs, batch_size))
        return tuple(
            FloatLike(float(index)) for index, _pair in enumerate(pairs, start=1)
        )


class FailingInferenceModel:
    def predict(
        self,
        pairs: tuple[tuple[str, str], ...],
        *,
        batch_size: int,
    ) -> tuple[float, ...]:
        raise RuntimeError("raw inference failure")


class MalformedCountModel:
    def predict(
        self,
        pairs: tuple[tuple[str, str], ...],
        *,
        batch_size: int,
    ) -> tuple[float, ...]:
        return (1.0,)


def test_local_reranker_accepts_valid_configuration() -> None:
    reranker = LocalCrossEncoderReranker(
        model_name="local-test-model",
        batch_size=8,
        _model_factory=lambda _model_name: FakeCrossEncoder(),
    )

    assert reranker.model_name == "local-test-model"
    assert reranker.batch_size == 8


@pytest.mark.parametrize("model_name", ["", "   "])
def test_local_reranker_rejects_blank_model_name(model_name: str) -> None:
    with pytest.raises(ValueError, match="model_name"):
        LocalCrossEncoderReranker(model_name=model_name)


@pytest.mark.parametrize("batch_size", [0, -1])
def test_local_reranker_rejects_non_positive_batch_size(batch_size: int) -> None:
    with pytest.raises(ValueError, match="batch_size"):
        LocalCrossEncoderReranker(batch_size=batch_size)


def test_local_reranker_does_not_load_model_during_construction() -> None:
    loaded_models: list[str] = []

    LocalCrossEncoderReranker(
        model_name="lazy-model",
        _model_factory=lambda model_name: loaded_models.append(model_name),
    )

    assert loaded_models == []


def test_local_reranker_loads_model_on_first_call() -> None:
    loaded_models: list[str] = []

    def factory(model_name: str) -> FakeCrossEncoder:
        loaded_models.append(model_name)
        return FakeCrossEncoder()

    reranker = LocalCrossEncoderReranker(
        model_name="lazy-model", _model_factory=factory
    )

    reranker.score((_request(),))

    assert loaded_models == ["lazy-model"]


def test_local_reranker_reuses_loaded_model() -> None:
    loaded_models: list[FakeCrossEncoder] = []

    def factory(_model_name: str) -> FakeCrossEncoder:
        model = FakeCrossEncoder()
        loaded_models.append(model)
        return model

    reranker = LocalCrossEncoderReranker(_model_factory=factory)

    reranker.score((_request(passage="first"),))
    reranker.score((_request(passage="second"),))

    assert len(loaded_models) == 1
    assert len(loaded_models[0].calls) == 2


def test_local_reranker_rejects_empty_input() -> None:
    reranker = LocalCrossEncoderReranker(
        _model_factory=lambda _model_name: FakeCrossEncoder()
    )

    with pytest.raises(ValueError, match="requests"):
        reranker.score(())


def test_local_reranker_passes_ordered_pairs_and_batch_size() -> None:
    model = FakeCrossEncoder()
    reranker = LocalCrossEncoderReranker(
        batch_size=2, _model_factory=lambda _model_name: model
    )
    requests = (_request(query="q1", passage="p1"), _request(query="q2", passage="p2"))

    reranker.score(requests)

    assert model.calls == [((("q1", "p1"), ("q2", "p2")), 2)]


def test_local_reranker_preserves_item_ids_and_order() -> None:
    first_id = uuid4()
    second_id = uuid4()
    reranker = LocalCrossEncoderReranker(
        _model_factory=lambda _model_name: FakeCrossEncoder()
    )

    scores = reranker.score((_request(item_id=first_id), _request(item_id=second_id)))

    assert [score.item_id for score in scores] == [first_id, second_id]
    assert [score.score for score in scores] == [1.0, 2.0]


def test_local_reranker_converts_numpy_like_scalars_to_builtin_floats() -> None:
    reranker = LocalCrossEncoderReranker(
        _model_factory=lambda _model_name: FakeCrossEncoder()
    )

    scores = reranker.score((_request(),))

    assert isinstance(scores, tuple)
    assert type(scores[0].score) is float


def test_local_reranker_wraps_loading_failures() -> None:
    def factory(_model_name: str) -> FakeCrossEncoder:
        raise RuntimeError("raw load failure")

    reranker = LocalCrossEncoderReranker(_model_factory=factory)

    with pytest.raises(LocalRerankingError, match="could not be loaded") as error:
        reranker.score((_request(),))

    assert isinstance(error.value.__cause__, RuntimeError)


def test_local_reranker_wraps_inference_failures() -> None:
    reranker = LocalCrossEncoderReranker(
        _model_factory=lambda _model_name: FailingInferenceModel()
    )

    with pytest.raises(LocalRerankingError, match="inference failed") as error:
        reranker.score((_request(),))

    assert isinstance(error.value.__cause__, RuntimeError)


def test_local_reranker_wraps_malformed_output_count() -> None:
    reranker = LocalCrossEncoderReranker(
        _model_factory=lambda _model_name: MalformedCountModel()
    )

    with pytest.raises(LocalRerankingError, match="unexpected number"):
        reranker.score((_request(), _request(passage="second")))


def test_local_reranker_satisfies_provider_protocol() -> None:
    reranker = LocalCrossEncoderReranker(
        _model_factory=lambda _model_name: FakeCrossEncoder()
    )

    assert isinstance(reranker, RerankerProvider)


def _request(
    *,
    item_id: object | None = None,
    query: str = "question",
    passage: str = "passage",
) -> RerankingRequest:
    return RerankingRequest(
        item_id=item_id or uuid4(),
        query=query,
        passage=passage,
    )
