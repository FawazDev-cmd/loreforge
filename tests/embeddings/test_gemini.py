from dataclasses import FrozenInstanceError
from math import inf, nan
from uuid import uuid4

import pytest

from loreforge.embeddings import (
    EmbeddingProvider,
    EmbeddingRequest,
    GeminiEmbeddingConfig,
    GeminiEmbeddingError,
    GeminiEmbeddingProvider,
    QueryEmbeddingProvider,
)


class FakeModels:
    def __init__(self, response: dict[str, object] | None = None) -> None:
        self.response = response or {
            "embeddings": [
                {"values": [1, 0.5]},
                {"values": [0.25, 0.75]},
            ]
        }
        self.calls: list[dict[str, object]] = []

    def embed_content(
        self,
        *,
        model: str,
        contents: list[str],
        config: object,
    ) -> dict[str, object]:
        self.calls.append({"model": model, "contents": contents, "config": config})
        return self.response


class FakeClient:
    def __init__(self, response: dict[str, object] | None = None) -> None:
        self.models = FakeModels(response)


class FailingModels:
    def embed_content(
        self,
        *,
        model: str,
        contents: list[str],
        config: object,
    ) -> dict[str, object]:
        raise RuntimeError("raw network failure with secret-key")


class FailingClient:
    models = FailingModels()


def test_gemini_embedding_config_accepts_valid_construction() -> None:
    config = GeminiEmbeddingConfig(
        api_key="key",
        model="gemini-embedding-001",
        timeout_seconds=9.5,
    )

    assert config.model == "gemini-embedding-001"
    assert config.timeout_seconds == 9.5


@pytest.mark.parametrize("api_key", ["", "   "])
def test_gemini_embedding_config_rejects_blank_api_key(api_key: str) -> None:
    with pytest.raises(ValueError, match="api_key"):
        GeminiEmbeddingConfig(api_key=api_key, model="model")


@pytest.mark.parametrize("model", ["", "   "])
def test_gemini_embedding_config_rejects_blank_model(model: str) -> None:
    with pytest.raises(ValueError, match="model"):
        GeminiEmbeddingConfig(api_key="key", model=model)


@pytest.mark.parametrize("timeout_seconds", [0.0, -1.0, nan, inf, -inf])
def test_gemini_embedding_config_rejects_invalid_timeout(
    timeout_seconds: float,
) -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        GeminiEmbeddingConfig(
            api_key="key",
            model="model",
            timeout_seconds=timeout_seconds,
        )


def test_gemini_embedding_config_rejects_non_float_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        GeminiEmbeddingConfig(api_key="key", model="model", timeout_seconds=1)  # type: ignore[arg-type]


def test_gemini_embedding_config_repr_excludes_api_key() -> None:
    config = GeminiEmbeddingConfig(api_key="secret-key", model="model")

    assert "secret-key" not in repr(config)


def test_gemini_embedding_config_is_immutable() -> None:
    config = GeminiEmbeddingConfig(api_key="key", model="model")

    with pytest.raises(FrozenInstanceError):
        config.model = "changed"


def test_gemini_embedding_provider_satisfies_protocols() -> None:
    provider = GeminiEmbeddingProvider(
        GeminiEmbeddingConfig(api_key="key", model="model"),
        client=FakeClient(),
    )

    assert isinstance(provider, EmbeddingProvider)
    assert isinstance(provider, QueryEmbeddingProvider)


def test_gemini_embedding_provider_preserves_request_ids_and_order() -> None:
    first_id = uuid4()
    second_id = uuid4()
    client = FakeClient()
    provider = GeminiEmbeddingProvider(
        GeminiEmbeddingConfig(
            api_key="key",
            model="gemini-embedding-001",
            timeout_seconds=2.5,
        ),
        client=client,
    )
    requests = (
        EmbeddingRequest(item_id=first_id, text="First chunk"),
        EmbeddingRequest(item_id=second_id, text="Second chunk"),
    )

    result = provider.embed_documents(requests)

    assert result.model == "gemini-embedding-001"
    assert result.dimensions == 2
    assert [vector.item_id for vector in result.vectors] == [first_id, second_id]
    assert result.vectors[0].values == (1.0, 0.5)
    assert result.vectors[1].values == (0.25, 0.75)
    assert client.models.calls[0]["model"] == "gemini-embedding-001"
    assert client.models.calls[0]["contents"] == ["First chunk", "Second chunk"]
    config = client.models.calls[0]["config"]
    assert getattr(config, "task_type") == "RETRIEVAL_DOCUMENT"
    assert getattr(getattr(config, "http_options"), "timeout") == 2500


def test_gemini_embedding_provider_embed_delegates_to_document_path() -> None:
    client = FakeClient(response={"embeddings": [{"values": [1, 2, 3]}]})
    provider = GeminiEmbeddingProvider(
        GeminiEmbeddingConfig(api_key="key", model="model"),
        client=client,
    )
    request = EmbeddingRequest(item_id=uuid4(), text="Chunk text")

    result = provider.embed((request,))

    assert result.vectors[0].item_id == request.item_id
    assert (
        getattr(client.models.calls[0]["config"], "task_type") == "RETRIEVAL_DOCUMENT"
    )


def test_gemini_embedding_provider_uses_query_task_for_query_embedding() -> None:
    client = FakeClient(response={"embeddings": [{"values": [0.1, 0.2]}]})
    provider = GeminiEmbeddingProvider(
        GeminiEmbeddingConfig(api_key="key", model="model"),
        client=client,
    )

    vector = provider.embed_query("What is covered?")

    assert vector.values == (0.1, 0.2)
    assert client.models.calls[0]["contents"] == ["What is covered?"]
    assert getattr(client.models.calls[0]["config"], "task_type") == "RETRIEVAL_QUERY"


def test_gemini_embedding_provider_rejects_empty_requests() -> None:
    provider = GeminiEmbeddingProvider(
        GeminiEmbeddingConfig(api_key="key", model="model"),
        client=FakeClient(),
    )

    with pytest.raises(ValueError, match="requests"):
        provider.embed_documents(())


def test_gemini_embedding_provider_rejects_mismatched_response_count() -> None:
    provider = GeminiEmbeddingProvider(
        GeminiEmbeddingConfig(api_key="key", model="model"),
        client=FakeClient(response={"embeddings": []}),
    )

    with pytest.raises(GeminiEmbeddingError, match="count"):
        provider.embed_documents((EmbeddingRequest(item_id=uuid4(), text="Chunk"),))


def test_gemini_embedding_provider_rejects_malformed_vectors() -> None:
    provider = GeminiEmbeddingProvider(
        GeminiEmbeddingConfig(api_key="key", model="model"),
        client=FakeClient(response={"embeddings": [{"values": ["bad"]}]}),
    )

    with pytest.raises(GeminiEmbeddingError, match="malformed"):
        provider.embed_documents((EmbeddingRequest(item_id=uuid4(), text="Chunk"),))


def test_gemini_embedding_provider_hides_raw_failure_details() -> None:
    provider = GeminiEmbeddingProvider(
        GeminiEmbeddingConfig(api_key="secret-key", model="model"),
        client=FailingClient(),
    )

    with pytest.raises(GeminiEmbeddingError) as exc_info:
        provider.embed_documents((EmbeddingRequest(item_id=uuid4(), text="Chunk"),))

    assert str(exc_info.value) == "gemini embedding request failed"
    assert "secret-key" not in str(exc_info.value)
