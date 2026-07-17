"""OpenRouter chat-completions language-model adapter."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from json import JSONDecodeError, dumps, loads
from math import isfinite
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from loreforge.generation.models import GenerationRequest, GenerationResponse

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterGenerationError(RuntimeError):
    """Raised when OpenRouter generation cannot complete safely."""


@dataclass(frozen=True, slots=True)
class OpenRouterConfig:
    """Configuration for the OpenRouter chat-completions adapter."""

    api_key: str = field(repr=False)
    model: str
    base_url: str = OPENROUTER_BASE_URL
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            msg = "api_key must not be empty"
            raise ValueError(msg)

        if not self.model.strip():
            msg = "model must not be empty"
            raise ValueError(msg)

        if not self.base_url.strip():
            msg = "base_url must not be empty"
            raise ValueError(msg)

        normalized_base_url = self.base_url.rstrip("/")
        parsed_url = urlparse(normalized_base_url)
        if parsed_url.scheme != "https":
            msg = "base_url must use https"
            raise ValueError(msg)

        timeout_seconds: object = self.timeout_seconds
        if type(timeout_seconds) is not float:
            msg = "timeout_seconds must be a float"
            raise ValueError(msg)

        if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0.0:
            msg = "timeout_seconds must be finite and greater than zero"
            raise ValueError(msg)

        object.__setattr__(self, "base_url", normalized_base_url)


class _JsonTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        """POST JSON and return a mapping-shaped JSON response."""
        ...


class _StdlibJsonTransport:
    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        request = Request(
            url,
            data=dumps(payload).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )

        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw_response = response.read().decode("utf-8")
        except HTTPError as error:
            msg = "openrouter HTTP request failed"
            raise OpenRouterGenerationError(msg) from error
        except (OSError, URLError, TimeoutError) as error:
            msg = "openrouter network request failed"
            raise OpenRouterGenerationError(msg) from error
        except UnicodeDecodeError as error:
            msg = "openrouter response was not valid UTF-8"
            raise OpenRouterGenerationError(msg) from error

        try:
            parsed_response = loads(raw_response)
        except JSONDecodeError as error:
            msg = "openrouter response was not valid JSON"
            raise OpenRouterGenerationError(msg) from error

        if not isinstance(parsed_response, Mapping):
            msg = "openrouter response JSON must be an object"
            raise OpenRouterGenerationError(msg)

        return cast(Mapping[str, object], parsed_response)


class OpenRouterLLMProvider:
    """LLM provider backed by OpenRouter chat completions."""

    def __init__(
        self,
        config: OpenRouterConfig,
        transport: _JsonTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport or _StdlibJsonTransport()

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate raw text for one provider-independent generation request."""
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, object] = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
            "stream": False,
        }

        try:
            response = self._transport.post_json(
                url=f"{self._config.base_url}/chat/completions",
                headers=headers,
                payload=payload,
                timeout_seconds=self._config.timeout_seconds,
            )
        except OpenRouterGenerationError:
            raise
        except Exception as error:
            msg = "openrouter request failed"
            raise OpenRouterGenerationError(msg) from error

        return _generation_response_from_payload(response)


def _generation_response_from_payload(
    payload: Mapping[str, object],
) -> GenerationResponse:
    model = _required_string(payload, "model")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        msg = "openrouter response choices must be a non-empty list"
        raise OpenRouterGenerationError(msg)

    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        msg = "openrouter response choice must be an object"
        raise OpenRouterGenerationError(msg)

    first_choice = cast(Mapping[str, object], first_choice)
    message = first_choice.get("message")
    if not isinstance(message, Mapping):
        msg = "openrouter response message must be an object"
        raise OpenRouterGenerationError(msg)

    message = cast(Mapping[str, object], message)
    content = _required_string(message, "content")
    finish_reason_value = first_choice.get("finish_reason")
    if finish_reason_value is None:
        finish_reason = None
    elif isinstance(finish_reason_value, str) and finish_reason_value.strip():
        finish_reason = finish_reason_value
    else:
        msg = "openrouter response finish_reason must be a nonblank string or null"
        raise OpenRouterGenerationError(msg)

    try:
        return GenerationResponse(
            text=content,
            model=model,
            finish_reason=finish_reason,
        )
    except ValueError as error:
        msg = "openrouter response failed generation validation"
        raise OpenRouterGenerationError(msg) from error


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        msg = f"openrouter response {key} must be a string"
        raise OpenRouterGenerationError(msg)

    if not value.strip():
        msg = f"openrouter response {key} must not be empty"
        raise OpenRouterGenerationError(msg)

    return value
