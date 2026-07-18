"""Application-level PDF ingestion-to-index orchestration."""

from typing import Protocol
from uuid import UUID

from loreforge.catalog import CatalogService, CatalogServiceError, DocumentStatus
from loreforge.documents.ingestion import IngestionResult, ingest_pdf
from loreforge.documents.models import DocumentChunk, DocumentSource
from loreforge.documents.upload import validate_pdf_upload
from loreforge.embeddings.pipeline import EmbeddedChunk, embed_chunks
from loreforge.embeddings.provider import EmbeddingProvider
from loreforge.indexing.errors import (
    DocumentAlreadyIndexedError,
    DocumentIndexingExecutionError,
)
from loreforge.indexing.models import IndexedDocumentResult
from loreforge.retrieval.bm25 import InMemoryBM25Index
from loreforge.vector_index import InMemoryVectorIndex

_INDEXING_FAILED = "document indexing failed"
_INDEXING_UNAVAILABLE = "document indexing is unavailable"
_ALREADY_INDEXED = "document is already indexed"
_NO_CHUNKS = "document produced no indexable chunks"


class PdfIngestor(Protocol):
    """Callable boundary for existing PDF ingestion orchestration."""

    def __call__(
        self,
        *,
        document_id: UUID,
        source: DocumentSource,
        content: bytes,
    ) -> IngestionResult:
        """Return parsed, normalized, and chunked PDF content."""
        ...


class DocumentIndexingService:
    """Index successfully ingested PDF chunks into semantic and lexical indexes."""

    def __init__(
        self,
        *,
        catalog_service: CatalogService,
        ingestor: PdfIngestor = ingest_pdf,
        embedding_provider: EmbeddingProvider | None = None,
        vector_index: InMemoryVectorIndex,
        lexical_index: InMemoryBM25Index,
    ) -> None:
        self._catalog_service = catalog_service
        self._ingestor = ingestor
        self._embedding_provider = embedding_provider
        self._vector_index = vector_index
        self._lexical_index = lexical_index

    def index_pdf(
        self,
        *,
        document_id: UUID,
        filename: str | None,
        media_type: str | None,
        content: bytes,
    ) -> IndexedDocumentResult:
        """Ingest, embed, and index one cataloged PDF document."""
        validated_upload = validate_pdf_upload(
            filename=filename,
            media_type=media_type,
            content=content,
        )
        source = DocumentSource(
            filename=validated_upload.filename,
            media_type=validated_upload.media_type,
            size_bytes=validated_upload.size_bytes,
        )
        self._validate_before_indexing(document_id)
        self._catalog_service.mark_ingesting(document_id)

        chunk_ids: tuple[UUID, ...] = ()
        try:
            ingestion_result = self._ingestor(
                document_id=document_id,
                source=source,
                content=content,
            )
            chunks = ingestion_result.chunks
            self._validate_ingestion_result(
                document_id=document_id,
                source=source,
                result=ingestion_result,
            )
            chunk_ids = tuple(chunk.chunk_id for chunk in chunks)
            embedded_chunks = self._embed_chunks(chunks)
            self._validate_embedded_chunks(
                document_id=document_id,
                chunk_ids=chunk_ids,
                embedded_chunks=embedded_chunks,
            )

            self._vector_index.add(embedded_chunks)
            self._lexical_index.add(chunks)
            self._catalog_service.mark_ready(
                document_id,
                page_count=len(ingestion_result.document.pages),
                chunk_count=len(chunks),
            )
        except DocumentIndexingExecutionError as exc:
            self._handle_failed_indexing(document_id, chunk_ids, exc)
        except Exception as exc:
            self._handle_failed_indexing(document_id, chunk_ids, exc)

        return IndexedDocumentResult(
            document_id=document_id,
            chunk_count=len(chunk_ids),
            semantic_indexed_count=len(chunk_ids),
            lexical_indexed_count=len(chunk_ids),
        )

    def _validate_before_indexing(self, document_id: UUID) -> None:
        entry = self._catalog_service.get(document_id)
        if entry is None:
            msg = "document_id does not exist in catalog"
            raise CatalogServiceError(msg)
        if entry.status is DocumentStatus.READY:
            raise DocumentAlreadyIndexedError(_ALREADY_INDEXED)

    def _validate_ingestion_result(
        self,
        *,
        document_id: UUID,
        source: DocumentSource,
        result: IngestionResult,
    ) -> None:
        if not result.chunks:
            raise DocumentIndexingExecutionError(_NO_CHUNKS)
        if result.document.document_id != document_id:
            raise DocumentIndexingExecutionError(_INDEXING_FAILED)
        if result.document.source != source:
            raise DocumentIndexingExecutionError(_INDEXING_FAILED)

        chunk_ids = tuple(chunk.chunk_id for chunk in result.chunks)
        if len(set(chunk_ids)) != len(chunk_ids):
            raise DocumentIndexingExecutionError(_INDEXING_FAILED)
        for chunk in result.chunks:
            if chunk.document_id != document_id:
                raise DocumentIndexingExecutionError(_INDEXING_FAILED)
            if chunk.source != source:
                raise DocumentIndexingExecutionError(_INDEXING_FAILED)

    def _embed_chunks(
        self,
        chunks: tuple[DocumentChunk, ...],
    ) -> tuple[EmbeddedChunk, ...]:
        if self._embedding_provider is None:
            raise DocumentIndexingExecutionError(_INDEXING_UNAVAILABLE)
        return embed_chunks(
            chunks=chunks,
            provider=self._embedding_provider,
        )

    def _validate_embedded_chunks(
        self,
        *,
        document_id: UUID,
        chunk_ids: tuple[UUID, ...],
        embedded_chunks: tuple[EmbeddedChunk, ...],
    ) -> None:
        embedded_ids = tuple(item.chunk.chunk_id for item in embedded_chunks)
        vector_ids = tuple(item.vector.item_id for item in embedded_chunks)
        if embedded_ids != chunk_ids or vector_ids != chunk_ids:
            raise DocumentIndexingExecutionError(_INDEXING_FAILED)
        for item in embedded_chunks:
            if item.chunk.document_id != document_id:
                raise DocumentIndexingExecutionError(_INDEXING_FAILED)

    def _handle_failed_indexing(
        self,
        document_id: UUID,
        chunk_ids: tuple[UUID, ...],
        original_error: Exception,
    ) -> None:
        self._rollback_indexes(chunk_ids)
        try:
            self._catalog_service.mark_failed(document_id)
        except Exception:
            pass
        raise DocumentIndexingExecutionError(_INDEXING_FAILED) from original_error

    def _rollback_indexes(self, chunk_ids: tuple[UUID, ...]) -> None:
        for chunk_id in chunk_ids:
            try:
                self._vector_index.remove(chunk_id)
            except Exception:
                pass
        for chunk_id in chunk_ids:
            try:
                self._lexical_index.remove(chunk_id)
            except Exception:
                pass
