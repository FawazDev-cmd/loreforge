"""Provider-independent language-model generation models."""

from dataclasses import dataclass
from math import isfinite

from loreforge.generation.prompting import PromptPackage


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Provider-independent prompt and generation limits."""

    system_prompt: str
    user_prompt: str
    max_output_tokens: int = 800
    temperature: float = 0.0

    def __post_init__(self) -> None:
        if not self.system_prompt.strip():
            msg = "system_prompt must not be empty"
            raise ValueError(msg)

        if not self.user_prompt.strip():
            msg = "user_prompt must not be empty"
            raise ValueError(msg)

        max_output_tokens: object = self.max_output_tokens
        if type(max_output_tokens) is not int:
            msg = "max_output_tokens must be an integer"
            raise ValueError(msg)

        if self.max_output_tokens <= 0:
            msg = "max_output_tokens must be greater than zero"
            raise ValueError(msg)

        temperature: object = self.temperature
        if type(temperature) is not float:
            msg = "temperature must be a float"
            raise ValueError(msg)

        if not isfinite(self.temperature):
            msg = "temperature must be finite"
            raise ValueError(msg)

        if not 0.0 <= self.temperature <= 2.0:
            msg = "temperature must be between 0.0 and 2.0"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class GenerationResponse:
    """Raw provider-generated text before answer validation or citation checks."""

    text: str
    model: str
    finish_reason: str | None

    def __post_init__(self) -> None:
        if not self.text.strip():
            msg = "text must not be empty"
            raise ValueError(msg)

        if not self.model.strip():
            msg = "model must not be empty"
            raise ValueError(msg)

        if self.finish_reason is not None and not self.finish_reason.strip():
            msg = "finish_reason must not be empty when provided"
            raise ValueError(msg)


def generation_request_from_prompt(
    prompt: PromptPackage,
    *,
    max_output_tokens: int = 800,
    temperature: float = 0.0,
) -> GenerationRequest:
    """Create a generation request from a prepared grounded prompt package."""
    return GenerationRequest(
        system_prompt=prompt.system_prompt,
        user_prompt=prompt.user_prompt,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )
