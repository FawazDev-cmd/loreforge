"""Document upload API routes."""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from loreforge.api.auth import get_current_principal
from loreforge.auth import AuthenticatedPrincipal
from loreforge.documents import DocumentSource
from loreforge.documents.upload import (
    MAX_UPLOAD_SIZE_BYTES,
    UnsupportedDocumentError,
    validate_pdf_upload,
)

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    filename: str
    media_type: str
    size_bytes: int
    status: str


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF file to accept")],
    _principal: Annotated[
        AuthenticatedPrincipal | None,
        Depends(get_current_principal),
    ],
) -> DocumentUploadResponse:
    try:
        content = await file.read(MAX_UPLOAD_SIZE_BYTES + 1)
        validated_upload = validate_pdf_upload(
            filename=file.filename,
            media_type=file.content_type,
            content=content,
        )
    except UnsupportedDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        status_code = status.HTTP_400_BAD_REQUEST
        if str(exc) == "uploaded file exceeds maximum size":
            status_code = status.HTTP_413_CONTENT_TOO_LARGE

        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    finally:
        await file.close()

    source = DocumentSource(
        filename=validated_upload.filename,
        media_type=validated_upload.media_type,
        size_bytes=validated_upload.size_bytes,
    )

    return DocumentUploadResponse(
        document_id=uuid4(),
        filename=source.filename,
        media_type=source.media_type,
        size_bytes=source.size_bytes,
        status="accepted",
    )
