"""Gemini generation provider backed by the Google Gen AI SDK."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from importlib import import_module
from math import isfinite
from typing import Any, Protocol, cast

from loreforge.generation.models import GenerationRequest, GenerationResponse


class GeminiGenerationError(RuntimeError):
    """Raised when Gemini generation cannot complete safely."""


@dataclass(frozen=True, slots=True)
class GeminiGenerationConfig:
    """Configuration for Gemini grounded-answer generation."""

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
    def generate_content(
        self,
        *,
        model: str,
        contents: str,
        config: Any,
    ) -> Any:
        """Generate content with Gemini."""
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


class GeminiLLMProvider:
    """LLM provider that calls Gemini through the Google Gen AI SDK."""

    def __init__(
        self,
        config: GeminiGenerationConfig,
        client: _GeminiClient | None = None,
    ) -> None:
        self._config = config
        self._client = client

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate raw text for one provider-independent generation request."""
        try:
            response = self._get_client().models.generate_content(
                model=self._config.model,
                contents=request.user_prompt,
                config=_generation_config(
                    request,
                    timeout_seconds=self._config.timeout_seconds,
                ),
            )
        except GeminiGenerationError:
            raise
        except Exception as error:
            msg = "gemini generation request failed"
            raise GeminiGenerationError(msg) from error

        return _generation_response_from_response(response, self._config.model)

    def _get_client(self) -> _GeminiClient:
        if self._client is None:
            self._client = create_gemini_client(
                api_key=self._config.api_key,
                timeout_seconds=self._config.timeout_seconds,
            )
        return self._client


def _generation_config(
    request: GenerationRequest,
    *,
    timeout_seconds: float,
) -> Any:
    types = import_module("google.genai.types")
    return types.GenerateContentConfig(
        system_instruction=request.system_prompt,
        max_output_tokens=request.max_output_tokens,
        temperature=request.temperature,
        http_options=types.HttpOptions(timeout=_timeout_milliseconds(timeout_seconds)),
    )


def _generation_response_from_response(
    response: Any,
    configured_model: str,
) -> GenerationResponse:
    text = _text_from_response(response)
    finish_reason = _finish_reason_from_response(response)
    try:
        return GenerationResponse(
            text=text,
            model=configured_model,
            finish_reason=finish_reason,
        )
    except ValueError as error:
        msg = "gemini generation response failed validation"
        raise GeminiGenerationError(msg) from error


def _text_from_response(response: Any) -> str:
    text = _field(response, "text")
    if not isinstance(text, str) or not text.strip():
        msg = "gemini generation response text was empty"
        raise GeminiGenerationError(msg)
    return text


def _finish_reason_from_response(response: Any) -> str | None:
    candidates = _field(response, "candidates")
    if not isinstance(candidates, Sequence) or isinstance(candidates, str):
        return None
    if not candidates:
        return None

    finish_reason = _field(candidates[0], "finish_reason")
    if finish_reason is None:
        return None

    value = getattr(finish_reason, "value", finish_reason)
    if not isinstance(value, str):
        value = str(value)
    if not value.strip():
        return None
    return value


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _timeout_milliseconds(timeout_seconds: float) -> int:
    return max(1, int(timeout_seconds * 1000))


__all__ = [
    "GeminiGenerationConfig",
    "GeminiGenerationError",
    "GeminiLLMProvider",
    "create_gemini_client",
]
