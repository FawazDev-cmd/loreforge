"""Grounded prompt and evidence-context construction."""

from loreforge.generation.answer_models import (
    GroundedAnswer,
    GroundedGenerationRequest,
    SourceReference,
)
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
from loreforge.generation.orchestration import (
    GroundedGenerationError,
    generate_grounded_answer,
    source_references_from_evidence,
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
    "GroundedAnswer",
    "GroundedGenerationError",
    "GroundedGenerationRequest",
    "LLMProvider",
    "OpenRouterConfig",
    "OpenRouterGenerationError",
    "OpenRouterLLMProvider",
    "PromptPackage",
    "SourceReference",
    "build_evidence_context",
    "build_grounded_prompt",
    "generate_grounded_answer",
    "generation_request_from_prompt",
    "source_references_from_evidence",
]
