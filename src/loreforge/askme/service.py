"""Framework-independent AskMe application service."""

from collections.abc import Callable
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from loreforge.askme.errors import (
    AskMeError,
    AskMeGroundingError,
    AskMeUnavailableError,
)
from loreforge.askme.models import AskMeCitation, AskMeRequest, AskMeResult
from loreforge.generation.answer_models import SourceReference
from loreforge.generation.validation_models import ValidatedGroundedAnswer

_GENERIC_GROUNDING_ERROR = "AskMe could not produce a safely grounded answer."
_GENERIC_UNAVAILABLE_ERROR = "AskMe is temporarily unavailable."


@runtime_checkable
class GroundedQueryEngine(Protocol):
    """Boundary for producing validated grounded answers."""

    def answer(self, question: str) -> ValidatedGroundedAnswer:
        """Answer a question with a validated grounded answer."""
        ...


class AskMeService:
    """Application service for safe end-user AskMe requests."""

    def __init__(
        self,
        *,
        query_engine: GroundedQueryEngine,
        request_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._query_engine = query_engine
        self._request_id_factory = request_id_factory

    def ask(self, request: AskMeRequest) -> AskMeResult:
        """Answer an AskMe request with validated source citations."""
        try:
            validated_answer = self._query_engine.answer(request.question)
        except AskMeError:
            raise
        except Exception as exc:
            raise AskMeUnavailableError(_GENERIC_UNAVAILABLE_ERROR) from exc

        self._validate_grounded_answer(validated_answer, request.question)
        request_id = self._new_request_id()
        grounded_answer = validated_answer.grounded_answer

        return AskMeResult(
            request_id=request_id,
            question=request.question,
            answer=grounded_answer.answer_text,
            citations=tuple(
                self._citation_from_source(source)
                for source in validated_answer.cited_sources
            ),
        )

    def _validate_grounded_answer(
        self,
        validated_answer: ValidatedGroundedAnswer,
        question: str,
    ) -> None:
        if type(validated_answer) is not ValidatedGroundedAnswer:
            raise AskMeGroundingError(_GENERIC_GROUNDING_ERROR)
        grounded_answer = validated_answer.grounded_answer
        if grounded_answer.question != question:
            raise AskMeGroundingError(_GENERIC_GROUNDING_ERROR)
        if grounded_answer.citations_validated is not True:
            raise AskMeGroundingError(_GENERIC_GROUNDING_ERROR)
        if validated_answer.citation_validation.is_valid is not True:
            raise AskMeGroundingError(_GENERIC_GROUNDING_ERROR)
        if not validated_answer.cited_sources:
            raise AskMeGroundingError(_GENERIC_GROUNDING_ERROR)

    def _new_request_id(self) -> UUID:
        request_id = self._request_id_factory()
        if type(request_id) is not UUID:
            raise AskMeGroundingError(_GENERIC_GROUNDING_ERROR)
        return request_id

    def _citation_from_source(self, source: SourceReference) -> AskMeCitation:
        return AskMeCitation(
            citation_id=source.citation_id,
            document_id=source.document_id,
            filename=source.filename,
            page_number=source.page_number,
            chunk_id=source.chunk_id,
        )
