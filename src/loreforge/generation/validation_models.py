"""Citation validation result models for grounded answers."""

from dataclasses import dataclass
from re import fullmatch

from loreforge.generation.answer_models import GroundedAnswer, SourceReference

_CITATION_ID_PATTERN = r"S[1-9][0-9]*"


@dataclass(frozen=True, slots=True)
class CitationExtraction:
    """Citation occurrences and unique citation IDs from generated text."""

    occurrences: tuple[str, ...]
    citation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for citation_id in (*self.occurrences, *self.citation_ids):
            _validate_citation_id(citation_id)

        if len(set(self.citation_ids)) != len(self.citation_ids):
            msg = "citation_ids must be unique"
            raise ValueError(msg)

        if self.citation_ids != _unique_first_occurrences(self.occurrences):
            msg = "citation_ids must match first-occurrence order"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class CitationValidationResult:
    """Deterministic citation support status against supplied sources."""

    citation_ids: tuple[str, ...]
    supported_citation_ids: tuple[str, ...]
    unsupported_citation_ids: tuple[str, ...]
    missing_citations: bool
    is_valid: bool

    def __post_init__(self) -> None:
        all_ids = (
            *self.citation_ids,
            *self.supported_citation_ids,
            *self.unsupported_citation_ids,
        )
        for citation_id in all_ids:
            _validate_citation_id(citation_id)

        for name, values in (
            ("citation_ids", self.citation_ids),
            ("supported_citation_ids", self.supported_citation_ids),
            ("unsupported_citation_ids", self.unsupported_citation_ids),
        ):
            if len(set(values)) != len(values):
                msg = f"{name} must contain unique values"
                raise ValueError(msg)

        supported = set(self.supported_citation_ids)
        unsupported = set(self.unsupported_citation_ids)
        if supported & unsupported:
            msg = "supported and unsupported citation IDs must not overlap"
            raise ValueError(msg)

        accounted = (*self.supported_citation_ids, *self.unsupported_citation_ids)
        if set(accounted) != set(self.citation_ids):
            msg = "supported and unsupported citation IDs must account for citation_ids"
            raise ValueError(msg)

        expected_supported = tuple(
            citation_id for citation_id in self.citation_ids if citation_id in supported
        )
        if self.supported_citation_ids != expected_supported:
            msg = "supported citation IDs must preserve citation order"
            raise ValueError(msg)

        expected_unsupported = tuple(
            citation_id
            for citation_id in self.citation_ids
            if citation_id in unsupported
        )
        if self.unsupported_citation_ids != expected_unsupported:
            msg = "unsupported citation IDs must preserve citation order"
            raise ValueError(msg)

        missing_citations: object = self.missing_citations
        if type(missing_citations) is not bool:
            msg = "missing_citations must be a boolean"
            raise ValueError(msg)

        is_valid: object = self.is_valid
        if type(is_valid) is not bool:
            msg = "is_valid must be a boolean"
            raise ValueError(msg)

        if self.missing_citations != (len(self.citation_ids) == 0):
            msg = "missing_citations must match citation_ids emptiness"
            raise ValueError(msg)

        expected_valid = (
            not self.missing_citations and not self.unsupported_citation_ids
        )
        if self.is_valid != expected_valid:
            msg = "is_valid must match missing and unsupported citation state"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ValidatedGroundedAnswer:
    """Grounded answer whose citation syntax references supplied sources."""

    grounded_answer: GroundedAnswer
    citation_validation: CitationValidationResult
    cited_sources: tuple[SourceReference, ...]

    def __post_init__(self) -> None:
        if self.grounded_answer.citations_validated is not True:
            msg = "grounded_answer must have citations_validated=True"
            raise ValueError(msg)

        if not self.citation_validation.is_valid:
            msg = "citation_validation must be valid"
            raise ValueError(msg)

        if not self.cited_sources:
            msg = "cited_sources must contain at least one source"
            raise ValueError(msg)

        citation_ids = tuple(source.citation_id for source in self.cited_sources)
        if len(set(citation_ids)) != len(citation_ids):
            msg = "cited source citation IDs must be unique"
            raise ValueError(msg)

        if citation_ids != self.citation_validation.citation_ids:
            msg = "cited source order must match citation validation order"
            raise ValueError(msg)

        source_by_id = {
            source.citation_id: source for source in self.grounded_answer.sources
        }
        for source in self.cited_sources:
            original = source_by_id.get(source.citation_id)
            if original is None:
                msg = "cited source must exist in grounded answer sources"
                raise ValueError(msg)
            if source != original:
                msg = "cited source must match original source exactly"
                raise ValueError(msg)


def _validate_citation_id(citation_id: str) -> None:
    if fullmatch(_CITATION_ID_PATTERN, citation_id) is None:
        msg = "citation ID must match S followed by a positive integer"
        raise ValueError(msg)


def _unique_first_occurrences(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)
