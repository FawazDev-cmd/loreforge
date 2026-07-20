from datetime import datetime, timezone
from uuid import UUID

import pytest

from loreforge.catalog import CatalogService, DocumentStatus, InMemoryCatalogRepository
from loreforge.documents.ingestion import IngestionResult
from loreforge.documents.models import (
    DocumentChunk,
    DocumentPage,
    DocumentSource,
    ParsedDocument,
)
from loreforge.embeddings.models import (
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingVector,
)
from loreforge.embeddings.pipeline import EmbeddedChunk
from loreforge.indexing import (
    DocumentAlreadyIndexedError,
    DocumentIndexingExecutionError,
    DocumentIndexingService,
    IndexingStatus,
    InMemoryIndexingStateRepository,
)
from loreforge.observability import InMemoryOperationalMetricsRecorder
from loreforge.retrieval.bm25 import BM25IndexError, InMemoryBM25Index
from loreforge.vector_index import InMemoryVectorIndex, VectorIndexError

DOC = UUID("00000000-0000-0000-0000-000000000001")
OTHER_DOC = UUID("00000000-0000-0000-0000-000000000002")
CHUNK1 = UUID("00000000-0000-0000-0000-000000000101")
CHUNK2 = UUID("00000000-0000-0000-0000-000000000102")
OTHER_CHUNK = UUID("00000000-0000-0000-0000-000000000201")
UPLOADED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
PDF_BYTES = b"%PDF- fake deterministic test bytes"
_DEFAULT_PROVIDER = object()


class FakeIngestor:
    def __init__(
        self,
        *,
        chunks: tuple[DocumentChunk, ...] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.chunks = chunks
        self.error = error
        self.calls: list[tuple[UUID, DocumentSource, bytes]] = []

    def __call__(
        self,
        *,
        document_id: UUID,
        source: DocumentSource,
        content: bytes,
    ) -> IngestionResult:
        self.calls.append((document_id, source, content))
        if self.error is not None:
            raise self.error
        chunks = (
            self.chunks if self.chunks is not None else _chunks(document_id, source)
        )
        return IngestionResult(
            document=ParsedDocument(
                document_id=document_id,
                source=source,
                pages=(DocumentPage(page_number=1, text="Refund policy text."),),
            ),
            chunks=chunks,
        )


class FakeEmbeddingProvider:
    def __init__(
        self,
        *,
        vectors: tuple[EmbeddingVector, ...] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.vectors = vectors
        self.error = error
        self.requests: list[tuple[EmbeddingRequest, ...]] = []

    def embed(self, requests: tuple[EmbeddingRequest, ...]) -> EmbeddingResult:
        self.requests.append(requests)
        if self.error is not None:
            raise self.error
        vectors = self.vectors or tuple(
            EmbeddingVector(item_id=request.item_id, values=(float(index + 1), 0.5))
            for index, request in enumerate(requests)
        )
        return EmbeddingResult(model="fake", dimensions=2, vectors=vectors)


class FailingVectorIndex(InMemoryVectorIndex):
    def __init__(self, *, fail_add: bool = False, fail_remove: bool = False) -> None:
        super().__init__()
        self.fail_add = fail_add
        self.fail_remove = fail_remove
        self.remove_calls: list[UUID] = []

    def add(self, items):  # type: ignore[no-untyped-def]
        if self.fail_add:
            raise VectorIndexError("raw vector failure")
        super().add(items)

    def remove(self, chunk_id: UUID) -> bool:
        self.remove_calls.append(chunk_id)
        removed = super().remove(chunk_id)
        if self.fail_remove:
            raise VectorIndexError("raw rollback failure")
        return removed


class FailingBM25Index(InMemoryBM25Index):
    def __init__(self, *, fail_add: bool = False, fail_remove: bool = False) -> None:
        super().__init__()
        self.fail_add = fail_add
        self.fail_remove = fail_remove
        self.remove_calls: list[UUID] = []

    def add(self, chunks):  # type: ignore[no-untyped-def]
        if self.fail_add:
            raise BM25IndexError("raw lexical failure")
        super().add(chunks)

    def remove(self, chunk_id: UUID) -> bool:
        self.remove_calls.append(chunk_id)
        removed = super().remove(chunk_id)
        if self.fail_remove:
            raise BM25IndexError("raw rollback failure")
        return removed


class ReadyFailingCatalogService(CatalogService):
    def __init__(self, repository: InMemoryCatalogRepository) -> None:
        super().__init__(repository)
        self.failed_documents: list[UUID] = []

    def mark_ready(
        self,
        document_id: UUID,
        *,
        page_count: int,
        chunk_count: int,
    ):
        raise RuntimeError("raw ready failure")

    def mark_failed(self, document_id: UUID):
        self.failed_documents.append(document_id)
        return super().mark_failed(document_id)


def test_successful_indexing_marks_ready_and_populates_both_indexes() -> None:
    harness = _harness()

    result = harness.service.index_pdf(
        document_id=DOC,
        filename="policy.pdf",
        media_type="application/pdf",
        content=PDF_BYTES,
    )

    assert result.document_id == DOC
    assert result.chunk_count == 2
    assert result.semantic_indexed_count == 2
    assert result.lexical_indexed_count == 2
    assert harness.catalog.get(DOC).status is DocumentStatus.READY  # type: ignore[union-attr]
    assert harness.catalog.get(DOC).chunk_count == 2  # type: ignore[union-attr]
    assert harness.vector_index.get(CHUNK1).chunk.chunk_id == CHUNK1  # type: ignore[union-attr]
    assert harness.lexical_index.get(CHUNK2).chunk_id == CHUNK2  # type: ignore[union-attr]


def test_ingestion_called_once_with_exact_source_and_content() -> None:
    harness = _harness()

    harness.service.index_pdf(
        document_id=DOC,
        filename="nested/path/policy.pdf",
        media_type="application/pdf",
        content=PDF_BYTES,
    )

    [(document_id, source, content)] = harness.ingestor.calls
    assert document_id == DOC
    assert source.filename == "policy.pdf"
    assert source.media_type == "application/pdf"
    assert source.size_bytes == len(PDF_BYTES)
    assert content == PDF_BYTES


def test_embedding_requests_preserve_chunk_order_text_and_ids() -> None:
    harness = _harness()

    harness.service.index_pdf(
        document_id=DOC,
        filename="policy.pdf",
        media_type="application/pdf",
        content=PDF_BYTES,
    )

    [requests] = harness.embedding_provider.requests
    assert tuple(request.item_id for request in requests) == (CHUNK1, CHUNK2)
    assert tuple(request.text for request in requests) == (
        "Refunds are allowed.",
        "Keep receipts.",
    )


def test_semantic_and_lexical_indexes_share_ingested_chunk_ids() -> None:
    harness = _harness()

    harness.service.index_pdf(
        document_id=DOC,
        filename="policy.pdf",
        media_type="application/pdf",
        content=PDF_BYTES,
    )

    semantic_ids = tuple(
        chunk_id for chunk_id in (CHUNK1, CHUNK2) if harness.vector_index.get(chunk_id)
    )
    lexical_ids = tuple(
        chunk_id for chunk_id in (CHUNK1, CHUNK2) if harness.lexical_index.get(chunk_id)
    )
    assert semantic_ids == lexical_ids == (CHUNK1, CHUNK2)


def test_source_identity_survives_indexing() -> None:
    harness = _harness()

    harness.service.index_pdf(
        document_id=DOC,
        filename="policy.pdf",
        media_type="application/pdf",
        content=PDF_BYTES,
    )

    indexed_chunk = harness.vector_index.get(CHUNK1).chunk  # type: ignore[union-attr]
    lexical_chunk = harness.lexical_index.get(CHUNK1)
    assert indexed_chunk.document_id == DOC
    assert indexed_chunk.chunk_id == CHUNK1
    assert indexed_chunk.source.filename == "policy.pdf"
    assert indexed_chunk.page_number == 1
    assert indexed_chunk.text == "Refunds are allowed."
    assert lexical_chunk == indexed_chunk


def test_ready_document_is_rejected_without_duplicate_records() -> None:
    harness = _harness()
    harness.service.index_pdf(
        document_id=DOC,
        filename="policy.pdf",
        media_type="application/pdf",
        content=PDF_BYTES,
    )

    with pytest.raises(DocumentAlreadyIndexedError):
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    assert harness.vector_index.size == 2
    assert harness.lexical_index.size == 2
    assert harness.catalog.get(DOC).status is DocumentStatus.READY  # type: ignore[union-attr]


def test_deleted_document_is_rejected_by_catalog_lifecycle() -> None:
    harness = _harness()
    harness.catalog.mark_failed(DOC)
    harness.catalog.mark_deleted(DOC)

    with pytest.raises(Exception, match="transition"):
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    assert harness.ingestor.calls == []


def test_unknown_document_raises_catalog_error_before_ingestion() -> None:
    harness = _harness(register=False)

    with pytest.raises(Exception, match="does not exist"):
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    assert harness.ingestor.calls == []


def test_missing_embedding_provider_marks_failed_without_index_writes() -> None:
    harness = _harness(embedding_provider=None)

    with pytest.raises(DocumentIndexingExecutionError) as exc_info:
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    assert "unavailable" not in str(exc_info.value)
    assert harness.catalog.get(DOC).status is DocumentStatus.FAILED  # type: ignore[union-attr]
    assert harness.vector_index.size == 0
    assert harness.lexical_index.size == 0


def test_ingestion_failure_marks_failed_and_does_not_embed() -> None:
    harness = _harness(ingestor=FakeIngestor(error=RuntimeError("raw pdf text")))

    with pytest.raises(DocumentIndexingExecutionError) as exc_info:
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    assert "raw pdf text" not in str(exc_info.value)
    assert harness.embedding_provider.requests == []
    assert harness.catalog.get(DOC).status is DocumentStatus.FAILED  # type: ignore[union-attr]


def test_zero_chunks_marks_failed_without_index_writes() -> None:
    source = _source()
    harness = _harness(ingestor=FakeIngestor(chunks=()))

    with pytest.raises(DocumentIndexingExecutionError):
        harness.service.index_pdf(
            document_id=DOC,
            filename=source.filename,
            media_type=source.media_type,
            content=PDF_BYTES,
        )

    assert harness.vector_index.size == 0
    assert harness.lexical_index.size == 0
    assert harness.catalog.get(DOC).status is DocumentStatus.FAILED  # type: ignore[union-attr]


def test_embedding_failure_marks_failed_without_index_writes() -> None:
    harness = _harness(
        embedding_provider=FakeEmbeddingProvider(error=RuntimeError("raw vector text"))
    )

    with pytest.raises(DocumentIndexingExecutionError) as exc_info:
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    assert "raw vector text" not in str(exc_info.value)
    assert harness.vector_index.size == 0
    assert harness.lexical_index.size == 0
    assert harness.catalog.get(DOC).status is DocumentStatus.FAILED  # type: ignore[union-attr]


def test_incomplete_embedding_output_marks_failed_before_index_mutation() -> None:
    harness = _harness(
        embedding_provider=FakeEmbeddingProvider(
            vectors=(EmbeddingVector(item_id=CHUNK1, values=(1.0, 0.5)),)
        )
    )

    with pytest.raises(DocumentIndexingExecutionError):
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    assert harness.vector_index.size == 0
    assert harness.lexical_index.size == 0
    assert harness.catalog.get(DOC).status is DocumentStatus.FAILED  # type: ignore[union-attr]


def test_semantic_insertion_failure_rolls_back_and_marks_failed() -> None:
    harness = _harness(vector_index=FailingVectorIndex(fail_add=True))

    with pytest.raises(DocumentIndexingExecutionError) as exc_info:
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    assert "raw vector failure" not in str(exc_info.value)
    assert harness.vector_index.size == 0
    assert harness.lexical_index.size == 0
    assert harness.catalog.get(DOC).status is DocumentStatus.FAILED  # type: ignore[union-attr]


def test_lexical_insertion_failure_rolls_back_semantic_records() -> None:
    harness = _harness(lexical_index=FailingBM25Index(fail_add=True))

    with pytest.raises(DocumentIndexingExecutionError):
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    assert harness.vector_index.size == 0
    assert harness.lexical_index.size == 0
    assert harness.catalog.get(DOC).status is DocumentStatus.FAILED  # type: ignore[union-attr]


def test_rollback_attempts_both_indexes_when_semantic_rollback_fails() -> None:
    vector_index = FailingVectorIndex(fail_remove=True)
    lexical_index = FailingBM25Index(fail_add=True)
    harness = _harness(vector_index=vector_index, lexical_index=lexical_index)

    with pytest.raises(DocumentIndexingExecutionError):
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    assert vector_index.remove_calls == [CHUNK1, CHUNK2]
    assert lexical_index.remove_calls == [CHUNK1, CHUNK2]
    assert vector_index.size == 0
    assert lexical_index.size == 0
    assert harness.catalog.get(DOC).status is DocumentStatus.FAILED  # type: ignore[union-attr]


def test_ready_transition_failure_rolls_back_both_indexes() -> None:
    repository = InMemoryCatalogRepository()
    catalog = ReadyFailingCatalogService(repository)
    catalog.register_upload(
        document_id=DOC,
        filename="policy.pdf",
        uploaded_at=UPLOADED_AT,
        page_count=0,
    )
    vector_index = InMemoryVectorIndex()
    lexical_index = InMemoryBM25Index()
    service = DocumentIndexingService(
        catalog_service=catalog,
        ingestor=FakeIngestor(),
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=vector_index,
        lexical_index=lexical_index,
    )

    with pytest.raises(DocumentIndexingExecutionError):
        service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    assert vector_index.size == 0
    assert lexical_index.size == 0
    assert catalog.failed_documents == [DOC]


def test_unrelated_indexed_document_survives_failed_indexing() -> None:
    lexical_index = FailingBM25Index()
    harness = _harness(lexical_index=lexical_index)
    other_source = DocumentSource("other.pdf", "application/pdf", len(PDF_BYTES))
    other_chunk = DocumentChunk(
        chunk_id=OTHER_CHUNK,
        document_id=OTHER_DOC,
        source=other_source,
        page_number=1,
        chunk_index=0,
        text="Unrelated policy text.",
    )
    other_vector = EmbeddingVector(item_id=OTHER_CHUNK, values=(9.0, 9.0))
    harness.vector_index.add((_embedded(other_chunk, other_vector),))
    harness.lexical_index.add((other_chunk,))
    lexical_index.fail_add = True

    with pytest.raises(DocumentIndexingExecutionError):
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    assert harness.vector_index.get(OTHER_CHUNK).chunk == other_chunk  # type: ignore[union-attr]
    assert harness.lexical_index.get(OTHER_CHUNK) == other_chunk
    assert harness.vector_index.get(CHUNK1) is None
    assert harness.lexical_index.get(CHUNK1) is None


def test_invalid_upload_is_rejected_before_lifecycle_change() -> None:
    harness = _harness()

    with pytest.raises(ValueError):
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=b"not a pdf",
        )

    assert harness.catalog.get(DOC).status is DocumentStatus.UPLOADED  # type: ignore[union-attr]
    assert harness.ingestor.calls == []


def test_input_content_is_not_mutated() -> None:
    harness = _harness()
    content = bytes(PDF_BYTES)

    harness.service.index_pdf(
        document_id=DOC,
        filename="policy.pdf",
        media_type="application/pdf",
        content=content,
    )

    assert content == PDF_BYTES


class Harness:
    def __init__(
        self,
        *,
        catalog: CatalogService,
        ingestor: FakeIngestor,
        embedding_provider: FakeEmbeddingProvider,
        vector_index: InMemoryVectorIndex,
        lexical_index: InMemoryBM25Index,
        service: DocumentIndexingService,
    ) -> None:
        self.catalog = catalog
        self.ingestor = ingestor
        self.embedding_provider = embedding_provider
        self.vector_index = vector_index
        self.lexical_index = lexical_index
        self.service = service


def _harness(
    *,
    register: bool = True,
    ingestor: FakeIngestor | None = None,
    embedding_provider: FakeEmbeddingProvider | None | object = _DEFAULT_PROVIDER,
    vector_index: InMemoryVectorIndex | None = None,
    lexical_index: InMemoryBM25Index | None = None,
    indexing_state_repository: InMemoryIndexingStateRepository | None = None,
    chunk_repository: object | None = None,
    embedding_repository: object | None = None,
    operational_metrics: InMemoryOperationalMetricsRecorder | None = None,
) -> Harness:
    catalog = CatalogService(InMemoryCatalogRepository())
    if register:
        catalog.register_upload(
            document_id=DOC,
            filename="policy.pdf",
            uploaded_at=UPLOADED_AT,
            page_count=0,
        )
    fake_ingestor = ingestor or FakeIngestor()
    fake_provider = (
        FakeEmbeddingProvider()
        if embedding_provider is _DEFAULT_PROVIDER
        else embedding_provider
    )
    semantic_index = vector_index or InMemoryVectorIndex()
    bm25_index = lexical_index or InMemoryBM25Index()
    service = DocumentIndexingService(
        catalog_service=catalog,
        ingestor=fake_ingestor,
        embedding_provider=fake_provider,
        vector_index=semantic_index,
        lexical_index=bm25_index,
        indexing_state_repository=indexing_state_repository,
        chunk_repository=chunk_repository,
        embedding_repository=embedding_repository,
        operational_metrics=operational_metrics,
    )
    return Harness(
        catalog=catalog,
        ingestor=fake_ingestor,
        embedding_provider=fake_provider,
        vector_index=semantic_index,
        lexical_index=bm25_index,
        service=service,
    )


def _source() -> DocumentSource:
    return DocumentSource("policy.pdf", "application/pdf", len(PDF_BYTES))


def _chunks(document_id: UUID, source: DocumentSource) -> tuple[DocumentChunk, ...]:
    return (
        DocumentChunk(
            chunk_id=CHUNK1,
            document_id=document_id,
            source=source,
            page_number=1,
            chunk_index=0,
            text="Refunds are allowed.",
        ),
        DocumentChunk(
            chunk_id=CHUNK2,
            document_id=document_id,
            source=source,
            page_number=1,
            chunk_index=1,
            text="Keep receipts.",
        ),
    )


def _embedded(chunk: DocumentChunk, vector: EmbeddingVector):
    from loreforge.embeddings.pipeline import EmbeddedChunk

    return EmbeddedChunk(chunk=chunk, vector=vector)


def test_successful_indexing_records_operational_metrics() -> None:
    operational_metrics = InMemoryOperationalMetricsRecorder()
    harness = _harness(operational_metrics=operational_metrics)

    harness.service.index_pdf(
        document_id=DOC,
        filename="policy.pdf",
        media_type="application/pdf",
        content=PDF_BYTES,
    )

    snapshot = operational_metrics.snapshot().as_dict()
    counters = {
        (item["name"], tuple(sorted(item["labels"].items()))): item["value"]
        for item in snapshot["counters"]
    }
    assert counters == {
        ("indexing_chunk_total", ()): 2,
        ("indexing_embedding_total", ()): 2,
        ("indexing_operation_total", (("success", "True"),)): 1,
    }
    assert snapshot["durations"][0]["name"] == "indexing_duration_ms"
    assert snapshot["durations"][0]["labels"] == {"success": "True"}


def test_failed_indexing_records_failure_operational_metrics() -> None:
    operational_metrics = InMemoryOperationalMetricsRecorder()
    harness = _harness(
        embedding_provider=FakeEmbeddingProvider(error=RuntimeError("raw secret")),
        operational_metrics=operational_metrics,
    )

    with pytest.raises(DocumentIndexingExecutionError):
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    snapshot = operational_metrics.snapshot().as_dict()
    assert snapshot["counters"] == [
        {"name": "indexing_chunk_total", "labels": {}, "value": 2},
        {
            "name": "indexing_operation_total",
            "labels": {"success": "False"},
            "value": 1,
        },
    ]
    assert snapshot["durations"][0]["labels"] == {"success": "False"}


def test_successful_indexing_records_indexing_state_metadata() -> None:
    indexing_states = InMemoryIndexingStateRepository()
    state_id = UUID("00000000-0000-0000-0000-000000000301")
    harness = _harness(indexing_state_repository=indexing_states)
    harness.service._indexing_state_id_factory = lambda: state_id
    harness.service._clock = lambda: UPLOADED_AT

    harness.service.index_pdf(
        document_id=DOC,
        filename="policy.pdf",
        media_type="application/pdf",
        content=PDF_BYTES,
    )

    [state] = indexing_states.list_for_document(DOC)
    assert state.state_id == state_id
    assert state.status is IndexingStatus.SUCCEEDED
    assert state.page_count == 1
    assert state.chunk_count == 2
    assert state.completed_at == UPLOADED_AT
    assert state.error_message is None


def test_failed_indexing_records_safe_failed_indexing_state() -> None:
    indexing_states = InMemoryIndexingStateRepository()
    state_id = UUID("00000000-0000-0000-0000-000000000302")
    harness = _harness(
        embedding_provider=FakeEmbeddingProvider(error=RuntimeError("raw provider")),
        indexing_state_repository=indexing_states,
    )
    harness.service._indexing_state_id_factory = lambda: state_id
    harness.service._clock = lambda: UPLOADED_AT

    with pytest.raises(DocumentIndexingExecutionError):
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    [state] = indexing_states.list_for_document(DOC)
    assert state.status is IndexingStatus.FAILED
    assert state.completed_at == UPLOADED_AT
    assert state.error_message == "document indexing failed"
    assert "raw provider" not in state.error_message


class RecordingChunkRepository:
    def __init__(self) -> None:
        self.chunks: dict[UUID, DocumentChunk] = {}
        self.removed: list[UUID] = []

    def add(self, chunks: tuple[DocumentChunk, ...]) -> None:
        for chunk in chunks:
            self.chunks[chunk.chunk_id] = chunk

    def get(self, chunk_id: UUID) -> DocumentChunk | None:
        return self.chunks.get(chunk_id)

    def list(self) -> tuple[DocumentChunk, ...]:
        return tuple(self.chunks.values())

    def list_for_document(self, document_id: UUID) -> tuple[DocumentChunk, ...]:
        return tuple(
            chunk for chunk in self.chunks.values() if chunk.document_id == document_id
        )

    def remove(self, chunk_id: UUID) -> bool:
        self.removed.append(chunk_id)
        return self.chunks.pop(chunk_id, None) is not None


class RecordingEmbeddingRepository:
    def __init__(self) -> None:
        self.embedded_chunks: dict[UUID, EmbeddedChunk] = {}
        self.removed: list[UUID] = []

    def add(self, embedded_chunks: tuple[EmbeddedChunk, ...]) -> None:
        for embedded_chunk in embedded_chunks:
            self.embedded_chunks[embedded_chunk.chunk.chunk_id] = embedded_chunk

    def get(self, chunk_id: UUID) -> EmbeddedChunk | None:
        return self.embedded_chunks.get(chunk_id)

    def list(self) -> tuple[EmbeddedChunk, ...]:
        return tuple(self.embedded_chunks.values())

    def list_for_document(self, document_id: UUID) -> tuple[EmbeddedChunk, ...]:
        return tuple(
            item
            for item in self.embedded_chunks.values()
            if item.chunk.document_id == document_id
        )

    def remove(self, chunk_id: UUID) -> bool:
        self.removed.append(chunk_id)
        return self.embedded_chunks.pop(chunk_id, None) is not None


def test_successful_indexing_persists_chunks_and_embeddings() -> None:
    chunk_repository = RecordingChunkRepository()
    embedding_repository = RecordingEmbeddingRepository()
    harness = _harness(
        chunk_repository=chunk_repository,
        embedding_repository=embedding_repository,
    )

    harness.service.index_pdf(
        document_id=DOC,
        filename="policy.pdf",
        media_type="application/pdf",
        content=PDF_BYTES,
    )

    assert tuple(chunk_repository.chunks) == (CHUNK1, CHUNK2)
    assert tuple(embedding_repository.embedded_chunks) == (CHUNK1, CHUNK2)
    assert (
        embedding_repository.embedded_chunks[CHUNK1].chunk
        == chunk_repository.chunks[CHUNK1]
    )


def test_failed_indexing_rolls_back_persisted_chunks_and_embeddings() -> None:
    chunk_repository = RecordingChunkRepository()
    embedding_repository = RecordingEmbeddingRepository()
    harness = _harness(
        lexical_index=FailingBM25Index(fail_add=True),
        chunk_repository=chunk_repository,
        embedding_repository=embedding_repository,
    )

    with pytest.raises(DocumentIndexingExecutionError):
        harness.service.index_pdf(
            document_id=DOC,
            filename="policy.pdf",
            media_type="application/pdf",
            content=PDF_BYTES,
        )

    assert chunk_repository.chunks == {}
    assert embedding_repository.embedded_chunks == {}
    assert chunk_repository.removed == [CHUNK1, CHUNK2]
    assert embedding_repository.removed == [CHUNK1, CHUNK2]
