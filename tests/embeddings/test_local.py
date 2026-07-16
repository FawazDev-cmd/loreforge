from uuid import uuid4

import pytest

from loreforge.embeddings import (
    EmbeddingProvider,
    EmbeddingRequest,
    LocalEmbeddingError,
    LocalSentenceTransformerProvider,
)


class FakeSentenceTransformer:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], int]] = []

    def encode_document(
        self,
        sentences: tuple[str, ...],
        *,
        batch_size: int,
    ) -> tuple[tuple[int, float], ...]:
        self.calls.append((sentences, batch_size))
        return tuple(
            (index, float(len(sentence)))
            for index, sentence in enumerate(sentences, start=1)
        )


class FailingInferenceModel:
    def encode_document(
        self,
        sentences: tuple[str, ...],
        *,
        batch_size: int,
    ) -> tuple[tuple[float, ...], ...]:
        raise RuntimeError("raw inference failure")


def test_local_provider_accepts_valid_configuration() -> None:
    provider = LocalSentenceTransformerProvider(
        model_name="local-test-model",
        batch_size=8,
        _model_factory=lambda _model_name: FakeSentenceTransformer(),
    )

    assert provider.model_name == "local-test-model"
    assert provider.batch_size == 8


@pytest.mark.parametrize("model_name", ["", "   "])
def test_local_provider_rejects_blank_model_name(model_name: str) -> None:
    with pytest.raises(ValueError, match="model_name"):
        LocalSentenceTransformerProvider(model_name=model_name)


@pytest.mark.parametrize("batch_size", [0, -1])
def test_local_provider_rejects_non_positive_batch_size(batch_size: int) -> None:
    with pytest.raises(ValueError, match="batch_size"):
        LocalSentenceTransformerProvider(batch_size=batch_size)


def test_local_provider_rejects_empty_requests() -> None:
    provider = LocalSentenceTransformerProvider(
        _model_factory=lambda _model_name: FakeSentenceTransformer(),
    )

    with pytest.raises(ValueError, match="requests"):
        provider.embed(())


def test_local_provider_does_not_load_model_during_construction() -> None:
    loaded_models: list[str] = []

    LocalSentenceTransformerProvider(
        model_name="lazy-model",
        _model_factory=lambda model_name: loaded_models.append(model_name),
    )

    assert loaded_models == []


def test_local_provider_loads_model_on_first_embedding_call() -> None:
    loaded_models: list[str] = []

    def factory(model_name: str) -> FakeSentenceTransformer:
        loaded_models.append(model_name)
        return FakeSentenceTransformer()

    provider = LocalSentenceTransformerProvider(
        model_name="lazy-model",
        _model_factory=factory,
    )

    provider.embed((EmbeddingRequest(item_id=uuid4(), text="Chunk text"),))

    assert loaded_models == ["lazy-model"]


def test_local_provider_reuses_loaded_model_across_calls() -> None:
    loaded_models: list[FakeSentenceTransformer] = []

    def factory(_model_name: str) -> FakeSentenceTransformer:
        model = FakeSentenceTransformer()
        loaded_models.append(model)
        return model

    provider = LocalSentenceTransformerProvider(_model_factory=factory)

    provider.embed((EmbeddingRequest(item_id=uuid4(), text="First chunk"),))
    provider.embed((EmbeddingRequest(item_id=uuid4(), text="Second chunk"),))

    assert len(loaded_models) == 1
    assert len(loaded_models[0].calls) == 2


def test_local_provider_passes_configured_batch_size_to_encoding() -> None:
    model = FakeSentenceTransformer()
    provider = LocalSentenceTransformerProvider(
        batch_size=2,
        _model_factory=lambda _model_name: model,
    )
    requests = (
        EmbeddingRequest(item_id=uuid4(), text="First chunk"),
        EmbeddingRequest(item_id=uuid4(), text="Second chunk"),
    )

    provider.embed(requests)

    assert model.calls == [(("First chunk", "Second chunk"), 2)]


def test_local_provider_preserves_request_ids_and_order() -> None:
    first_id = uuid4()
    second_id = uuid4()
    provider = LocalSentenceTransformerProvider(
        _model_factory=lambda _model_name: FakeSentenceTransformer(),
    )

    result = provider.embed(
        (
            EmbeddingRequest(item_id=first_id, text="First chunk"),
            EmbeddingRequest(item_id=second_id, text="Second chunk"),
        )
    )

    assert [vector.item_id for vector in result.vectors] == [first_id, second_id]


def test_local_provider_returns_builtin_float_tuples_and_dimensions() -> None:
    provider = LocalSentenceTransformerProvider(
        model_name="local-test-model",
        _model_factory=lambda _model_name: FakeSentenceTransformer(),
    )
    item_id = uuid4()

    result = provider.embed((EmbeddingRequest(item_id=item_id, text="abc"),))

    assert result.model == "local-test-model"
    assert result.dimensions == 2
    assert result.vectors[0].item_id == item_id
    assert result.vectors[0].values == (1.0, 3.0)
    assert isinstance(result.vectors[0].values, tuple)
    assert all(type(value) is float for value in result.vectors[0].values)


def test_local_provider_satisfies_embedding_provider_protocol() -> None:
    provider = LocalSentenceTransformerProvider(
        _model_factory=lambda _model_name: FakeSentenceTransformer(),
    )

    assert isinstance(provider, EmbeddingProvider)


def test_local_provider_wraps_model_loading_failures() -> None:
    def factory(_model_name: str) -> FakeSentenceTransformer:
        raise RuntimeError("raw load failure")

    provider = LocalSentenceTransformerProvider(_model_factory=factory)

    with pytest.raises(LocalEmbeddingError, match="could not be loaded") as error:
        provider.embed((EmbeddingRequest(item_id=uuid4(), text="Chunk text"),))

    assert isinstance(error.value.__cause__, RuntimeError)


def test_local_provider_wraps_inference_failures() -> None:
    provider = LocalSentenceTransformerProvider(
        _model_factory=lambda _model_name: FailingInferenceModel(),
    )

    with pytest.raises(LocalEmbeddingError, match="inference failed") as error:
        provider.embed((EmbeddingRequest(item_id=uuid4(), text="Chunk text"),))

    assert isinstance(error.value.__cause__, RuntimeError)
