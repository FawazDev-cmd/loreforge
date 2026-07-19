"""Application-level PDF ingestion-to-index orchestration."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

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
from loreforge.indexing.state import (
    IndexingState,
    IndexingStateRepository,
    IndexingStatus,
)
from loreforge.retrieval.bm25 import InMemoryBM25Index
from loreforge.retrieval.repository import ChunkRepository, EmbeddingRepository
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
        indexing_state_repository: IndexingStateRepository | None = None,
        chunk_repository: ChunkRepository | None = None,
        embedding_repository: EmbeddingRepository | None = None,
        indexing_state_id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._catalog_service = catalog_service
        self._ingestor = ingestor
        self._embedding_provider = embedding_provider
        self._vector_index = vector_index
        self._lexical_index = lexical_index
        self._indexing_state_repository = indexing_state_repository
        self._chunk_repository = chunk_repository
        self._embedding_repository = embedding_repository
        self._indexing_state_id_factory = indexing_state_id_factory
        self._clock = clock or _utc_now

    def index_pdf(
        self,
        *,
        document_id: UUID,
        filename: str | None,
        media_type: str | None,
        content: bytes,
        owner_user_id: UUID | None = None,
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
        self._validate_before_indexing(document_id, owner_user_id)
        if owner_user_id is None:
            self._catalog_service.mark_ingesting(document_id)
        else:
            self._catalog_service.mark_ingesting_for_owner(
                document_id,
                owner_user_id,
            )
        indexing_state_id = self._start_indexing_state(document_id)

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
            self._persist_chunks(chunks, owner_user_id)
            embedded_chunks = self._embed_chunks(chunks)
            self._validate_embedded_chunks(
                document_id=document_id,
                chunk_ids=chunk_ids,
                embedded_chunks=embedded_chunks,
            )
            self._persist_embeddings(embedded_chunks)

            self._vector_index.add(embedded_chunks)
            self._lexical_index.add(chunks)
            page_count = len(ingestion_result.document.pages)
            chunk_count = len(chunks)
            if owner_user_id is None:
                self._catalog_service.mark_ready(
                    document_id,
                    page_count=page_count,
                    chunk_count=chunk_count,
                )
            else:
                self._catalog_service.mark_ready_for_owner(
                    document_id,
                    owner_user_id,
                    page_count=page_count,
                    chunk_count=chunk_count,
                )
            self._complete_indexing_state(
                indexing_state_id,
                page_count=page_count,
                chunk_count=chunk_count,
            )
        except DocumentIndexingExecutionError as exc:
            self._handle_failed_indexing(document_id, chunk_ids, indexing_state_id, exc)
        except Exception as exc:
            self._handle_failed_indexing(document_id, chunk_ids, indexing_state_id, exc)

        return IndexedDocumentResult(
            document_id=document_id,
            chunk_count=len(chunk_ids),
            semantic_indexed_count=len(chunk_ids),
            lexical_indexed_count=len(chunk_ids),
        )

    def _validate_before_indexing(
        self,
        document_id: UUID,
        owner_user_id: UUID | None,
    ) -> None:
        if owner_user_id is None:
            entry = self._catalog_service.get(document_id)
        else:
            entry = self._catalog_service.get_for_owner(document_id, owner_user_id)
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
        indexing_state_id: UUID | None,
        original_error: Exception,
    ) -> None:
        self._rollback_indexes(chunk_ids)
        self._rollback_persistence(chunk_ids)
        self._fail_indexing_state(indexing_state_id)
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

    def _persist_chunks(
        self,
        chunks: tuple[DocumentChunk, ...],
        owner_user_id: UUID | None,
    ) -> None:
        if self._chunk_repository is None:
            return
        if owner_user_id is None:
            self._chunk_repository.add(chunks)
        else:
            self._chunk_repository.add(chunks, owner_user_id=owner_user_id)

    def _persist_embeddings(self, embedded_chunks: tuple[EmbeddedChunk, ...]) -> None:
        if self._embedding_repository is None:
            return
        self._embedding_repository.add(embedded_chunks)

    def _rollback_persistence(self, chunk_ids: tuple[UUID, ...]) -> None:
        for chunk_id in chunk_ids:
            if self._embedding_repository is not None:
                try:
                    self._embedding_repository.remove(chunk_id)
                except Exception:
                    pass
        for chunk_id in chunk_ids:
            if self._chunk_repository is not None:
                try:
                    self._chunk_repository.remove(chunk_id)
                except Exception:
                    pass

    def _start_indexing_state(self, document_id: UUID) -> UUID | None:
        if self._indexing_state_repository is None:
            return None
        now = self._clock()
        state_id = self._indexing_state_id_factory()
        self._indexing_state_repository.add(
            IndexingState(
                state_id=state_id,
                document_id=document_id,
                status=IndexingStatus.STARTED,
                started_at=now,
                updated_at=now,
            )
        )
        return state_id

    def _complete_indexing_state(
        self,
        state_id: UUID | None,
        *,
        page_count: int,
        chunk_count: int,
    ) -> None:
        if self._indexing_state_repository is None or state_id is None:
            return
        state = self._indexing_state_repository.get(state_id)
        if state is None:
            return
        now = self._clock()
        self._indexing_state_repository.update(
            replace(
                state,
                status=IndexingStatus.SUCCEEDED,
                updated_at=now,
                completed_at=now,
                page_count=page_count,
                chunk_count=chunk_count,
            )
        )

    def _fail_indexing_state(self, state_id: UUID | None) -> None:
        if self._indexing_state_repository is None or state_id is None:
            return
        state = self._indexing_state_repository.get(state_id)
        if state is None:
            return
        now = self._clock()
        try:
            self._indexing_state_repository.update(
                replace(
                    state,
                    status=IndexingStatus.FAILED,
                    updated_at=now,
                    completed_at=now,
                    error_message=_INDEXING_FAILED,
                )
            )
        except Exception:
            pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
