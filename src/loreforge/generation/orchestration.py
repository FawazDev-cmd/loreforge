"""Framework-independent grounded-answer generation orchestration."""

from loreforge.generation.answer_models import (
    GroundedAnswer,
    GroundedGenerationRequest,
    SourceReference,
)
from loreforge.generation.evidence import (
    EvidenceContext,
    EvidenceContextConfig,
    build_evidence_context,
)
from loreforge.generation.models import generation_request_from_prompt
from loreforge.generation.prompting import build_grounded_prompt
from loreforge.generation.provider import LLMProvider


class GroundedGenerationError(ValueError):
    """Raised when grounded-generation orchestration reaches an invalid state."""


def source_references_from_evidence(
    evidence: EvidenceContext,
) -> tuple[SourceReference, ...]:
    """Create source references for every evidence item supplied to generation."""
    return tuple(
        SourceReference(
            citation_id=item.citation_id,
            document_id=item.document_id,
            chunk_id=item.chunk_id,
            filename=item.filename,
            page_number=item.page_number,
        )
        for item in evidence.items
    )


def generate_grounded_answer(
    *,
    request: GroundedGenerationRequest,
    provider: LLMProvider,
) -> GroundedAnswer:
    """Generate one raw grounded answer from reranked evidence and an LLM provider."""
    evidence = build_evidence_context(
        candidates=request.candidates,
        config=EvidenceContextConfig(max_characters=request.evidence_max_characters),
    )
    prompt = build_grounded_prompt(question=request.question, evidence=evidence)
    generation_request = generation_request_from_prompt(
        prompt,
        max_output_tokens=request.max_output_tokens,
        temperature=request.temperature,
    )
    generation_response = provider.generate(generation_request)
    sources = source_references_from_evidence(evidence)

    if not sources:
        msg = "grounded generation produced no source references"
        raise GroundedGenerationError(msg)

    return GroundedAnswer(
        question=request.question,
        answer_text=generation_response.text,
        sources=sources,
        evidence=evidence,
        provider_model=generation_response.model,
        finish_reason=generation_response.finish_reason,
        citations_validated=False,
    )
