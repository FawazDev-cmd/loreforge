from dataclasses import FrozenInstanceError
from math import inf, nan
from typing import Any

import pytest

from loreforge.generation import (
    GenerationRequest,
    GenerationResponse,
    LLMProvider,
    OpenRouterConfig,
    OpenRouterGenerationError,
    OpenRouterLLMProvider,
)


class FakeTransport:
    def __init__(self, response: dict[str, object] | None = None) -> None:
        self.response = response or _valid_response()
        self.calls: list[dict[str, object]] = []

    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.response


class FailingTransport:
    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        raise ValueError("network failure with no secrets")


def test_openrouter_config_accepts_valid_construction() -> None:
    config = OpenRouterConfig(api_key="key", model="model")

    assert config.model == "model"
    assert config.base_url == "https://openrouter.ai/api/v1"
    assert config.timeout_seconds == 30.0


def test_openrouter_config_normalizes_trailing_slash() -> None:
    config = OpenRouterConfig(
        api_key="key", model="model", base_url="https://example.test/api/"
    )

    assert config.base_url == "https://example.test/api"


@pytest.mark.parametrize("api_key", ["", "   "])
def test_openrouter_config_rejects_blank_api_key(api_key: str) -> None:
    with pytest.raises(ValueError, match="api_key"):
        OpenRouterConfig(api_key=api_key, model="model")


@pytest.mark.parametrize("model", ["", "   "])
def test_openrouter_config_rejects_blank_model(model: str) -> None:
    with pytest.raises(ValueError, match="model"):
        OpenRouterConfig(api_key="key", model=model)


@pytest.mark.parametrize("base_url", ["", "   "])
def test_openrouter_config_rejects_blank_base_url(base_url: str) -> None:
    with pytest.raises(ValueError, match="base_url"):
        OpenRouterConfig(api_key="key", model="model", base_url=base_url)


def test_openrouter_config_rejects_non_https_base_url() -> None:
    with pytest.raises(ValueError, match="https"):
        OpenRouterConfig(
            api_key="key", model="model", base_url="http://example.test/api"
        )


@pytest.mark.parametrize("timeout_seconds", [0.0, -1.0, nan, inf, -inf])
def test_openrouter_config_rejects_invalid_timeout(timeout_seconds: float) -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        OpenRouterConfig(api_key="key", model="model", timeout_seconds=timeout_seconds)


def test_openrouter_config_rejects_integer_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        OpenRouterConfig(api_key="key", model="model", timeout_seconds=1)  # type: ignore[arg-type]


def test_openrouter_config_rejects_boolean_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        OpenRouterConfig(api_key="key", model="model", timeout_seconds=True)  # type: ignore[arg-type]


def test_openrouter_config_repr_excludes_api_key() -> None:
    config = OpenRouterConfig(api_key="secret-key", model="model")

    assert "secret-key" not in repr(config)


def test_openrouter_config_is_immutable() -> None:
    config = OpenRouterConfig(api_key="key", model="model")

    with pytest.raises(FrozenInstanceError):
        config.model = "changed"


def test_openrouter_provider_constructor_performs_no_request() -> None:
    transport = FakeTransport()

    OpenRouterLLMProvider(_config(), transport=transport)

    assert transport.calls == []


def test_openrouter_provider_uses_correct_endpoint() -> None:
    transport = FakeTransport()
    provider = OpenRouterLLMProvider(_config(), transport=transport)

    provider.generate(_request())

    assert transport.calls[0]["url"] == "https://example.test/api/chat/completions"


def test_openrouter_provider_sends_bearer_authorization_header() -> None:
    transport = FakeTransport()
    provider = OpenRouterLLMProvider(_config(api_key="secret"), transport=transport)

    provider.generate(_request())

    headers = _call_headers(transport)
    assert headers["Authorization"] == "Bearer secret"


def test_openrouter_provider_sends_json_content_type_header() -> None:
    transport = FakeTransport()
    provider = OpenRouterLLMProvider(_config(), transport=transport)

    provider.generate(_request())

    headers = _call_headers(transport)
    assert headers["Content-Type"] == "application/json"


def test_openrouter_provider_sends_configured_model() -> None:
    transport = FakeTransport()
    provider = OpenRouterLLMProvider(_config(model="custom-model"), transport=transport)

    provider.generate(_request())

    assert _call_payload(transport)["model"] == "custom-model"


def test_openrouter_provider_preserves_separate_system_and_user_messages() -> None:
    transport = FakeTransport()
    provider = OpenRouterLLMProvider(_config(), transport=transport)

    provider.generate(_request(system_prompt="system exact", user_prompt="user exact"))

    assert _call_payload(transport)["messages"] == [
        {"role": "system", "content": "system exact"},
        {"role": "user", "content": "user exact"},
    ]


def test_openrouter_provider_forwards_temperature() -> None:
    transport = FakeTransport()
    provider = OpenRouterLLMProvider(_config(), transport=transport)

    provider.generate(_request(temperature=0.75))

    assert _call_payload(transport)["temperature"] == 0.75


def test_openrouter_provider_forwards_max_tokens() -> None:
    transport = FakeTransport()
    provider = OpenRouterLLMProvider(_config(), transport=transport)

    provider.generate(_request(max_output_tokens=123))

    assert _call_payload(transport)["max_tokens"] == 123


def test_openrouter_provider_sets_stream_false() -> None:
    transport = FakeTransport()
    provider = OpenRouterLLMProvider(_config(), transport=transport)

    provider.generate(_request())

    assert _call_payload(transport)["stream"] is False


def test_openrouter_provider_forwards_timeout() -> None:
    transport = FakeTransport()
    provider = OpenRouterLLMProvider(_config(timeout_seconds=9.5), transport=transport)

    provider.generate(_request())

    assert transport.calls[0]["timeout_seconds"] == 9.5


def test_openrouter_provider_calls_transport_once() -> None:
    transport = FakeTransport()
    provider = OpenRouterLLMProvider(_config(), transport=transport)

    provider.generate(_request())

    assert len(transport.calls) == 1


def test_openrouter_provider_satisfies_llm_provider() -> None:
    assert isinstance(
        OpenRouterLLMProvider(_config(), transport=FakeTransport()), LLMProvider
    )


def test_openrouter_provider_repeated_calls_use_same_transport() -> None:
    transport = FakeTransport()
    provider = OpenRouterLLMProvider(_config(), transport=transport)

    provider.generate(_request())
    provider.generate(_request(user_prompt="other"))

    assert len(transport.calls) == 2


def test_openrouter_provider_repr_excludes_api_key() -> None:
    provider = OpenRouterLLMProvider(
        _config(api_key="secret-key"), transport=FakeTransport()
    )

    assert "secret-key" not in repr(provider)


def test_openrouter_provider_converts_valid_response() -> None:
    response = OpenRouterLLMProvider(_config(), transport=FakeTransport()).generate(
        _request()
    )

    assert response == GenerationResponse(
        text="Generated answer.", model="openrouter-model", finish_reason="stop"
    )


def test_openrouter_provider_preserves_response_model() -> None:
    transport = FakeTransport(response=_valid_response(model="provider-model"))

    response = OpenRouterLLMProvider(_config(), transport=transport).generate(
        _request()
    )

    assert response.model == "provider-model"


def test_openrouter_provider_preserves_response_text_exactly() -> None:
    text = "  Exact generated text.\n"
    transport = FakeTransport(response=_valid_response(content=text))

    response = OpenRouterLLMProvider(_config(), transport=transport).generate(
        _request()
    )

    assert response.text == text


def test_openrouter_provider_preserves_finish_reason() -> None:
    transport = FakeTransport(response=_valid_response(finish_reason="length"))

    response = OpenRouterLLMProvider(_config(), transport=transport).generate(
        _request()
    )

    assert response.finish_reason == "length"


def test_openrouter_provider_accepts_none_finish_reason() -> None:
    transport = FakeTransport(response=_valid_response(finish_reason=None))

    response = OpenRouterLLMProvider(_config(), transport=transport).generate(
        _request()
    )

    assert response.finish_reason is None


def test_openrouter_provider_ignores_unrelated_response_fields() -> None:
    response_payload = _valid_response()
    response_payload["usage"] = {"total_tokens": 10}

    response = OpenRouterLLMProvider(
        _config(), transport=FakeTransport(response=response_payload)
    ).generate(_request())

    assert response.text == "Generated answer."


@pytest.mark.parametrize(
    "response",
    [
        {"model": "model", "choices": []},
        {"model": "model"},
        {"model": "model", "choices": ["bad"]},
        {"model": "model", "choices": [{}]},
        {"model": "model", "choices": [{"message": "bad"}]},
        {"model": "model", "choices": [{"message": {}}]},
        {"model": "model", "choices": [{"message": {"content": "   "}}]},
        {"model": "model", "choices": [{"message": {"content": None}}]},
        {"choices": [{"message": {"content": "answer"}}]},
        {"model": "   ", "choices": [{"message": {"content": "answer"}}]},
        {
            "model": "model",
            "choices": [{"message": {"content": "answer"}, "finish_reason": "   "}],
        },
    ],
)
def test_openrouter_provider_rejects_malformed_responses(
    response: dict[str, object],
) -> None:
    provider = OpenRouterLLMProvider(
        _config(), transport=FakeTransport(response=response)
    )

    with pytest.raises(OpenRouterGenerationError):
        provider.generate(_request())


def test_openrouter_provider_wraps_transport_failures() -> None:
    provider = OpenRouterLLMProvider(_config(), transport=FailingTransport())

    with pytest.raises(OpenRouterGenerationError, match="request") as error:
        provider.generate(
            _request(system_prompt="private prompt", user_prompt="secret user")
        )

    assert isinstance(error.value.__cause__, ValueError)


def test_openrouter_errors_do_not_expose_api_key_prompts_or_content() -> None:
    transport = FakeTransport(response=_valid_response(content={"secret": "response"}))
    provider = OpenRouterLLMProvider(_config(api_key="secret-key"), transport=transport)

    with pytest.raises(OpenRouterGenerationError) as error:
        provider.generate(
            _request(system_prompt="private prompt", user_prompt="secret user")
        )

    message = str(error.value)
    assert "secret-key" not in message
    assert "private prompt" not in message
    assert "secret user" not in message
    assert "secret response" not in message


def _config(
    *,
    api_key: str = "test-key",
    model: str = "test-model",
    timeout_seconds: float = 3.0,
) -> OpenRouterConfig:
    return OpenRouterConfig(
        api_key=api_key,
        model=model,
        base_url="https://example.test/api/",
        timeout_seconds=timeout_seconds,
    )


def _request(
    *,
    system_prompt: str = "system",
    user_prompt: str = "user",
    max_output_tokens: int = 800,
    temperature: float = 0.0,
) -> GenerationRequest:
    return GenerationRequest(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )


def _valid_response(
    *,
    model: str = "openrouter-model",
    content: object = "Generated answer.",
    finish_reason: object = "stop",
) -> dict[str, object]:
    return {
        "model": model,
        "choices": [
            {
                "message": {"content": content},
                "finish_reason": finish_reason,
            }
        ],
    }


def _call_payload(transport: FakeTransport) -> dict[str, object]:
    return _cast_dict(transport.calls[0]["payload"])


def _call_headers(transport: FakeTransport) -> dict[str, str]:
    return _cast_dict(transport.calls[0]["headers"])


def _cast_dict(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return value
