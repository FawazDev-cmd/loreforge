"""Administrative catalog API routes."""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from loreforge.catalog import (
    CatalogEntry,
    CatalogService,
    CatalogServiceError,
    DocumentStatus,
    InMemoryCatalogRepository,
)

router = APIRouter(prefix="/admin", tags=["admin"])

_catalog_service = CatalogService(InMemoryCatalogRepository())


class CreateDocumentRequest(BaseModel):
    """Transport model for registering catalog metadata."""

    filename: str
    page_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)

    @field_validator("filename")
    @classmethod
    def filename_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "filename must not be empty"
            raise ValueError(msg)
        return value


class DocumentCountsRequest(BaseModel):
    """Transport model for final document counts."""

    page_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)


class DocumentResponse(BaseModel):
    """Transport model for catalog document responses."""

    document_id: UUID
    filename: str
    uploaded_at: datetime
    page_count: int
    chunk_count: int
    status: DocumentStatus


class DocumentListResponse(BaseModel):
    """Transport model for ordered catalog document lists."""

    documents: tuple[DocumentResponse, ...]


def get_catalog_service() -> CatalogService:
    """Return the process-local catalog service."""
    return _catalog_service


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> DocumentListResponse:
    return DocumentListResponse(
        documents=tuple(_document_response(entry) for entry in service.list())
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> DocumentResponse:
    entry = service.get(document_id)
    if entry is None:
        raise _not_found()
    return _document_response(entry)


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    request: CreateDocumentRequest,
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> DocumentResponse:
    try:
        entry = service.register_upload(
            document_id=_new_document_id(),
            filename=request.filename,
            uploaded_at=_utc_now(),
            page_count=request.page_count,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return _document_response(entry)


@router.post("/documents/{document_id}/ingesting", response_model=DocumentResponse)
def mark_document_ingesting(
    document_id: UUID,
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> DocumentResponse:
    return _transition_document(lambda: service.mark_ingesting(document_id))


@router.post("/documents/{document_id}/ready", response_model=DocumentResponse)
def mark_document_ready(
    document_id: UUID,
    request: DocumentCountsRequest,
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> DocumentResponse:
    return _transition_document(
        lambda: service.mark_ready(
            document_id,
            page_count=request.page_count,
            chunk_count=request.chunk_count,
        )
    )


@router.post("/documents/{document_id}/failed", response_model=DocumentResponse)
def mark_document_failed(
    document_id: UUID,
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> DocumentResponse:
    return _transition_document(lambda: service.mark_failed(document_id))


@router.post("/documents/{document_id}/deleted", response_model=DocumentResponse)
def mark_document_deleted(
    document_id: UUID,
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> DocumentResponse:
    return _transition_document(lambda: service.mark_deleted(document_id))


def _document_response(entry: CatalogEntry) -> DocumentResponse:
    return DocumentResponse(
        document_id=entry.document_id,
        filename=entry.filename,
        uploaded_at=entry.uploaded_at,
        page_count=entry.page_count,
        chunk_count=entry.chunk_count,
        status=entry.status,
    )


def _transition_document(operation: Callable[[], CatalogEntry]) -> DocumentResponse:
    try:
        entry = operation()
    except CatalogServiceError as exc:
        if "does not exist" in str(exc):
            raise _not_found() from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return _document_response(entry)


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="document not found",
    )


def _new_document_id() -> UUID:
    return uuid4()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
