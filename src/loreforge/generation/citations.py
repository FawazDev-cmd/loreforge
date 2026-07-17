"""Citation extraction and enforcement for grounded answers."""

from dataclasses import replace
from re import compile

from loreforge.generation.answer_models import GroundedAnswer, SourceReference
from loreforge.generation.validation_models import (
    CitationExtraction,
    CitationValidationResult,
    ValidatedGroundedAnswer,
)

_CITATION_MARKER_PATTERN = compile(r"(?<!\[)\[(S[1-9][0-9]*)\](?!\])")


class CitationEnforcementError(ValueError):
    """Raised when answer citations fail deterministic enforcement."""


def extract_citations(answer_text: str) -> CitationExtraction:
    """Extract LoreForge citation IDs from generated answer text."""
    if not answer_text.strip():
        msg = "answer_text must not be empty"
        raise ValueError(msg)

    occurrences = tuple(
        match.group(1) for match in _CITATION_MARKER_PATTERN.finditer(answer_text)
    )
    seen: set[str] = set()
    citation_ids: list[str] = []
    for citation_id in occurrences:
        if citation_id not in seen:
            seen.add(citation_id)
            citation_ids.append(citation_id)

    return CitationExtraction(occurrences=occurrences, citation_ids=tuple(citation_ids))


def validate_citations(
    *,
    extraction: CitationExtraction,
    sources: tuple[SourceReference, ...],
) -> CitationValidationResult:
    """Validate extracted citations against available source references."""
    if not sources:
        msg = "sources must contain at least one source"
        raise ValueError(msg)

    source_ids = tuple(source.citation_id for source in sources)
    if len(set(source_ids)) != len(source_ids):
        msg = "source citation IDs must be unique"
        raise ValueError(msg)

    supported_source_ids = set(source_ids)
    supported = tuple(
        citation_id
        for citation_id in extraction.citation_ids
        if citation_id in supported_source_ids
    )
    unsupported = tuple(
        citation_id
        for citation_id in extraction.citation_ids
        if citation_id not in supported_source_ids
    )

    return CitationValidationResult(
        citation_ids=extraction.citation_ids,
        supported_citation_ids=supported,
        unsupported_citation_ids=unsupported,
        missing_citations=not extraction.citation_ids,
        is_valid=bool(extraction.citation_ids) and not unsupported,
    )


def validate_grounded_answer(answer: GroundedAnswer) -> ValidatedGroundedAnswer:
    """Enforce citation presence and source support for a grounded answer."""
    extraction = extract_citations(answer.answer_text)
    validation = validate_citations(extraction=extraction, sources=answer.sources)

    if validation.missing_citations:
        msg = "answer contains no supported citation markers"
        raise CitationEnforcementError(msg)

    if validation.unsupported_citation_ids:
        msg = "answer contains unsupported citation IDs"
        raise CitationEnforcementError(msg)

    source_by_id = {source.citation_id: source for source in answer.sources}
    cited_sources = tuple(
        source_by_id[citation_id] for citation_id in validation.citation_ids
    )
    validated_answer = replace(answer, citations_validated=True)

    return ValidatedGroundedAnswer(
        grounded_answer=validated_answer,
        citation_validation=validation,
        cited_sources=cited_sources,
    )
