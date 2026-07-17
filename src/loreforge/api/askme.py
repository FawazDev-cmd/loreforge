"""AskMe end-user query API route."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from loreforge.askme import (
    AskMeGroundingError,
    AskMeRequest,
    AskMeResult,
    AskMeService,
    AskMeUnavailableError,
)
from loreforge.generation.validation_models import ValidatedGroundedAnswer

router = APIRouter(tags=["askme"])

_UNAVAILABLE_DETAIL = "AskMe is temporarily unavailable."
_GROUNDING_DETAIL = "AskMe could not produce a safely grounded answer."


class AskRequest(BaseModel):
    """Transport model for an AskMe question."""

    question: str

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "question must not be empty"
            raise ValueError(msg)
        return value


class CitationResponse(BaseModel):
    """Transport model for one returned source citation."""

    citation_id: str
    document_id: UUID
    filename: str
    page_number: int
    chunk_id: UUID


class AskResponse(BaseModel):
    """Transport model for an AskMe answer."""

    request_id: UUID
    question: str
    answer: str
    citations: list[CitationResponse]


class _UnavailableGroundedQueryEngine:
    def answer(self, question: str) -> ValidatedGroundedAnswer:
        raise AskMeUnavailableError(_UNAVAILABLE_DETAIL)


def get_askme_service() -> AskMeService:
    """Return the default unconfigured AskMe service."""
    return AskMeService(query_engine=_UnavailableGroundedQueryEngine())


@router.post("/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    service: Annotated[AskMeService, Depends(get_askme_service)],
) -> AskResponse:
    try:
        result = service.ask(AskMeRequest(question=request.question))
    except AskMeUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_UNAVAILABLE_DETAIL,
        ) from exc
    except AskMeGroundingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_GROUNDING_DETAIL,
        ) from exc

    return _ask_response(result)


def _ask_response(result: AskMeResult) -> AskResponse:
    return AskResponse(
        request_id=result.request_id,
        question=result.question,
        answer=result.answer,
        citations=[
            CitationResponse(
                citation_id=citation.citation_id,
                document_id=citation.document_id,
                filename=citation.filename,
                page_number=citation.page_number,
                chunk_id=citation.chunk_id,
            )
            for citation in result.citations
        ],
    )
