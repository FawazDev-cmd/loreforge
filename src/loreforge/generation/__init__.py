"""Grounded prompt and evidence-context construction."""

from loreforge.generation.evidence import (
    EvidenceContext,
    EvidenceContextConfig,
    EvidenceContextError,
    EvidenceItem,
    build_evidence_context,
)
from loreforge.generation.models import (
    GenerationRequest,
    GenerationResponse,
    generation_request_from_prompt,
)
from loreforge.generation.openrouter import (
    OpenRouterConfig,
    OpenRouterGenerationError,
    OpenRouterLLMProvider,
)
from loreforge.generation.prompting import PromptPackage, build_grounded_prompt
from loreforge.generation.provider import LLMProvider

__all__ = [
    "EvidenceContext",
    "EvidenceContextConfig",
    "EvidenceContextError",
    "EvidenceItem",
    "GenerationRequest",
    "GenerationResponse",
    "LLMProvider",
    "OpenRouterConfig",
    "OpenRouterGenerationError",
    "OpenRouterLLMProvider",
    "PromptPackage",
    "build_evidence_context",
    "build_grounded_prompt",
    "generation_request_from_prompt",
]
