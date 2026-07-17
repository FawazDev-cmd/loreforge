"""Language-model provider protocol."""

from typing import Protocol, runtime_checkable

from loreforge.generation.models import GenerationRequest, GenerationResponse


@runtime_checkable
class LLMProvider(Protocol):
    """Replaceable provider that generates raw text from a prompt request."""

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Return one raw generation response for the supplied request."""
        ...
