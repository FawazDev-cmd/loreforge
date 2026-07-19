from dataclasses import FrozenInstanceError
from enum import Enum
from math import inf, nan

import pytest

from loreforge.generation import (
    GeminiGenerationConfig,
    GeminiGenerationError,
    GeminiLLMProvider,
    GenerationRequest,
    LLMProvider,
)


class FinishReason(Enum):
    STOP = "STOP"


class FakeCandidate:
    finish_reason = FinishReason.STOP


class FakeResponse:
    text = "Grounded answer [S1]."
    candidates = [FakeCandidate()]


class FakeModels:
    def __init__(self, response: object | None = None) -> None:
        self.response = response or FakeResponse()
        self.calls: list[dict[str, object]] = []

    def generate_content(
        self,
        *,
        model: str,
        contents: str,
        config: object,
    ) -> object:
        self.calls.append({"model": model, "contents": contents, "config": config})
        return self.response


class FakeClient:
    def __init__(self, response: object | None = None) -> None:
        self.models = FakeModels(response)


class FailingModels:
    def generate_content(
        self,
        *,
        model: str,
        contents: str,
        config: object,
    ) -> object:
        raise RuntimeError("raw provider failure with secret-key")


class FailingClient:
    models = FailingModels()


def test_gemini_generation_config_accepts_valid_construction() -> None:
    config = GeminiGenerationConfig(
        api_key="key",
        model="gemini-2.5-flash",
        timeout_seconds=7.5,
    )

    assert config.model == "gemini-2.5-flash"
    assert config.timeout_seconds == 7.5


@pytest.mark.parametrize("api_key", ["", "   "])
def test_gemini_generation_config_rejects_blank_api_key(api_key: str) -> None:
    with pytest.raises(ValueError, match="api_key"):
        GeminiGenerationConfig(api_key=api_key, model="model")


@pytest.mark.parametrize("model", ["", "   "])
def test_gemini_generation_config_rejects_blank_model(model: str) -> None:
    with pytest.raises(ValueError, match="model"):
        GeminiGenerationConfig(api_key="key", model=model)


@pytest.mark.parametrize("timeout_seconds", [0.0, -1.0, nan, inf, -inf])
def test_gemini_generation_config_rejects_invalid_timeout(
    timeout_seconds: float,
) -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        GeminiGenerationConfig(
            api_key="key",
            model="model",
            timeout_seconds=timeout_seconds,
        )


def test_gemini_generation_config_rejects_non_float_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        GeminiGenerationConfig(api_key="key", model="model", timeout_seconds=1)  # type: ignore[arg-type]


def test_gemini_generation_config_repr_excludes_api_key() -> None:
    config = GeminiGenerationConfig(api_key="secret-key", model="model")

    assert "secret-key" not in repr(config)


def test_gemini_generation_config_is_immutable() -> None:
    config = GeminiGenerationConfig(api_key="key", model="model")

    with pytest.raises(FrozenInstanceError):
        config.model = "changed"


def test_gemini_generation_provider_satisfies_protocol() -> None:
    provider = GeminiLLMProvider(
        GeminiGenerationConfig(api_key="key", model="model"),
        client=FakeClient(),
    )

    assert isinstance(provider, LLMProvider)


def test_gemini_generation_provider_maps_generation_request() -> None:
    client = FakeClient()
    provider = GeminiLLMProvider(
        GeminiGenerationConfig(
            api_key="key",
            model="gemini-2.5-flash",
            timeout_seconds=3.0,
        ),
        client=client,
    )
    request = GenerationRequest(
        system_prompt="Use only evidence.",
        user_prompt="Answer with citations.",
        max_output_tokens=123,
        temperature=0.5,
    )

    response = provider.generate(request)

    assert response.text == "Grounded answer [S1]."
    assert response.model == "gemini-2.5-flash"
    assert response.finish_reason == "STOP"
    assert client.models.calls == [
        {
            "model": "gemini-2.5-flash",
            "contents": "Answer with citations.",
            "config": client.models.calls[0]["config"],
        }
    ]
    config = client.models.calls[0]["config"]
    assert getattr(config, "system_instruction") == "Use only evidence."
    assert getattr(config, "max_output_tokens") == 123
    assert getattr(config, "temperature") == 0.5
    assert getattr(getattr(config, "http_options"), "timeout") == 3000


def test_gemini_generation_provider_allows_missing_finish_reason() -> None:
    provider = GeminiLLMProvider(
        GeminiGenerationConfig(api_key="key", model="model"),
        client=FakeClient(response={"text": "Answer [S1]."}),
    )

    response = provider.generate(
        GenerationRequest(system_prompt="System", user_prompt="User")
    )

    assert response.finish_reason is None


@pytest.mark.parametrize(
    "response",
    [
        {"text": ""},
        {"text": "   "},
        {"candidates": []},
    ],
)
def test_gemini_generation_provider_rejects_empty_text(response: object) -> None:
    provider = GeminiLLMProvider(
        GeminiGenerationConfig(api_key="key", model="model"),
        client=FakeClient(response=response),
    )

    with pytest.raises(GeminiGenerationError, match="text"):
        provider.generate(GenerationRequest(system_prompt="System", user_prompt="User"))


def test_gemini_generation_provider_hides_raw_failure_details() -> None:
    provider = GeminiLLMProvider(
        GeminiGenerationConfig(api_key="secret-key", model="model"),
        client=FailingClient(),
    )

    with pytest.raises(GeminiGenerationError) as exc_info:
        provider.generate(GenerationRequest(system_prompt="System", user_prompt="User"))

    assert str(exc_info.value) == "gemini generation request failed"
    assert "secret-key" not in str(exc_info.value)
