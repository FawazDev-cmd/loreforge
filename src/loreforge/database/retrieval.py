"""SQLAlchemy adapters for durable retrieval repositories."""

from uuid import UUID

from sqlalchemy import Select, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from loreforge.database.engine import SessionFactory
from loreforge.database.models import (
    DocumentChunkRecord,
    EmbeddingRecord,
    RetrievalMetadataRecord,
)
from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.embeddings import EmbeddingVector
from loreforge.embeddings.pipeline import EmbeddedChunk
from loreforge.retrieval.bm25 import InMemoryBM25Index
from loreforge.retrieval.filters import RetrievalFilter
from loreforge.retrieval.lexical_models import (
    LexicalSearchRequest,
    LexicalSearchResponse,
)
from loreforge.retrieval.repository import RetrievalRepositoryError
from loreforge.vector_index import InMemoryVectorIndex, VectorSearchResult


class SqlAlchemyChunkRepository:
    """Durable document-chunk repository backed by SQLAlchemy sessions."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(
        self,
        chunks: tuple[DocumentChunk, ...],
        owner_user_id: UUID | None = None,
    ) -> None:
        if not chunks:
            msg = "chunks must contain at least one chunk"
            raise RetrievalRepositoryError(msg)
        records = tuple(_chunk_record(chunk, owner_user_id) for chunk in chunks)
        metadata_records = tuple(
            _metadata_record(chunk, owner_user_id) for chunk in chunks
        )
        try:
            with self._session_factory() as session, session.begin():
                session.add_all([*records, *metadata_records])
        except IntegrityError as exc:
            msg = "chunk_id already exists in retrieval storage"
            raise RetrievalRepositoryError(msg) from exc

    def get(self, chunk_id: UUID) -> DocumentChunk | None:
        with self._session_factory() as session:
            record = _get_chunk_record(session, chunk_id)
            if record is None:
                return None
            return _chunk_from_record(record)

    def list(
        self,
        filters: RetrievalFilter = RetrievalFilter(),
    ) -> tuple[DocumentChunk, ...]:
        statement = _filtered_chunk_statement(filters).order_by(
            DocumentChunkRecord.row_id
        )
        with self._session_factory() as session:
            return tuple(
                _chunk_from_record(record) for record in session.scalars(statement)
            )

    def list_for_document(self, document_id: UUID) -> tuple[DocumentChunk, ...]:
        return self.list(RetrievalFilter(document_ids=(document_id,)))

    def remove(self, chunk_id: UUID) -> bool:
        with self._session_factory() as session, session.begin():
            record = _get_chunk_record(session, chunk_id)
            if record is None:
                return False
            session.execute(
                delete(EmbeddingRecord).where(EmbeddingRecord.chunk_id == chunk_id)
            )
            session.execute(
                delete(RetrievalMetadataRecord).where(
                    RetrievalMetadataRecord.chunk_id == chunk_id
                )
            )
            session.delete(record)
            return True


class SqlAlchemyEmbeddingRepository:
    """Durable embedding repository backed by SQLAlchemy sessions."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(self, embedded_chunks: tuple[EmbeddedChunk, ...]) -> None:
        if not embedded_chunks:
            msg = "embedded_chunks must contain at least one embedded chunk"
            raise RetrievalRepositoryError(msg)
        records = tuple(_embedding_record(item) for item in embedded_chunks)
        try:
            with self._session_factory() as session, session.begin():
                session.add_all(records)
        except IntegrityError as exc:
            msg = "chunk_id already exists in embedding storage"
            raise RetrievalRepositoryError(msg) from exc

    def get(self, chunk_id: UUID) -> EmbeddedChunk | None:
        with self._session_factory() as session:
            return _embedded_chunk_from_session(session, chunk_id)

    def list(
        self,
        filters: RetrievalFilter = RetrievalFilter(),
    ) -> tuple[EmbeddedChunk, ...]:
        statement = _filtered_embedding_statement(filters).order_by(
            EmbeddingRecord.row_id
        )
        with self._session_factory() as session:
            return tuple(
                _embedded_chunk_from_records(chunk, embedding)
                for chunk, embedding in session.execute(statement)
            )

    def list_for_document(self, document_id: UUID) -> tuple[EmbeddedChunk, ...]:
        return self.list(RetrievalFilter(document_ids=(document_id,)))

    def remove(self, chunk_id: UUID) -> bool:
        with self._session_factory() as session, session.begin():
            statement = select(EmbeddingRecord).where(
                EmbeddingRecord.chunk_id == chunk_id
            )
            record = session.scalar(statement)
            if record is None:
                return False
            session.delete(record)
            return True


class SqlAlchemyRetrievalRepository:
    """Repository-backed lexical and vector retrieval over durable records."""

    def __init__(
        self,
        *,
        chunk_repository: SqlAlchemyChunkRepository,
        embedding_repository: SqlAlchemyEmbeddingRepository,
    ) -> None:
        self._chunk_repository = chunk_repository
        self._embedding_repository = embedding_repository

    def lexical_search(
        self,
        request: LexicalSearchRequest,
        filters: RetrievalFilter = RetrievalFilter(),
    ) -> LexicalSearchResponse:
        chunks = self._chunk_repository.list(filters)
        if not chunks:
            return LexicalSearchResponse(query=request.query, results=())
        index = InMemoryBM25Index()
        index.add(chunks)
        return index.search(request)

    def vector_search(
        self,
        *,
        query_vector: tuple[float, ...],
        top_k: int,
        filters: RetrievalFilter = RetrievalFilter(),
    ) -> tuple[VectorSearchResult, ...]:
        if top_k <= 0:
            msg = "top_k must be greater than zero"
            raise RetrievalRepositoryError(msg)
        embedded_chunks = self._embedding_repository.list(filters)
        if not embedded_chunks:
            return ()
        index = InMemoryVectorIndex()
        index.add(embedded_chunks)
        return index.search(query_vector=query_vector, top_k=top_k)


def _chunk_record(
    chunk: DocumentChunk,
    owner_user_id: UUID | None,
) -> DocumentChunkRecord:
    return DocumentChunkRecord(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        source_filename=chunk.source.filename,
        source_media_type=chunk.source.media_type,
        source_size_bytes=chunk.source.size_bytes,
        owner_user_id=owner_user_id,
        page_number=chunk.page_number,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
    )


def _metadata_record(
    chunk: DocumentChunk,
    owner_user_id: UUID | None,
) -> RetrievalMetadataRecord:
    return RetrievalMetadataRecord(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        filename=chunk.source.filename,
        owner_user_id=owner_user_id,
        page_number=chunk.page_number,
        chunk_index=chunk.chunk_index,
    )


def _embedding_record(item: EmbeddedChunk) -> EmbeddingRecord:
    values = list(item.vector.values)
    return EmbeddingRecord(
        chunk_id=item.chunk.chunk_id,
        dimensions=len(values),
        values=values,
    )


def _get_chunk_record(session: Session, chunk_id: UUID) -> DocumentChunkRecord | None:
    statement = select(DocumentChunkRecord).where(
        DocumentChunkRecord.chunk_id == chunk_id
    )
    return session.scalar(statement)


def _chunk_from_record(record: DocumentChunkRecord) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=record.chunk_id,
        document_id=record.document_id,
        source=DocumentSource(
            filename=record.source_filename,
            media_type=record.source_media_type,
            size_bytes=record.source_size_bytes,
        ),
        page_number=record.page_number,
        chunk_index=record.chunk_index,
        text=record.text,
    )


def _embedded_chunk_from_session(
    session: Session,
    chunk_id: UUID,
) -> EmbeddedChunk | None:
    statement = (
        select(DocumentChunkRecord, EmbeddingRecord)
        .join(EmbeddingRecord, EmbeddingRecord.chunk_id == DocumentChunkRecord.chunk_id)
        .where(EmbeddingRecord.chunk_id == chunk_id)
    )
    row = session.execute(statement).one_or_none()
    if row is None:
        return None
    chunk, embedding = row
    return _embedded_chunk_from_records(chunk, embedding)


def _embedded_chunk_from_records(
    chunk_record: DocumentChunkRecord,
    embedding_record: EmbeddingRecord,
) -> EmbeddedChunk:
    values = tuple(float(value) for value in embedding_record.values)
    return EmbeddedChunk(
        chunk=_chunk_from_record(chunk_record),
        vector=EmbeddingVector(item_id=chunk_record.chunk_id, values=values),
    )


def _filtered_chunk_statement(
    filters: RetrievalFilter,
) -> Select[tuple[DocumentChunkRecord]]:
    statement = select(DocumentChunkRecord)
    if filters.document_ids:
        statement = statement.where(
            DocumentChunkRecord.document_id.in_(filters.document_ids)
        )
    if filters.filenames:
        statement = statement.where(
            DocumentChunkRecord.source_filename.in_(filters.filenames)
        )
    if filters.owner_user_ids:
        statement = statement.where(
            DocumentChunkRecord.owner_user_id.in_(filters.owner_user_ids)
        )
    return statement


def _filtered_embedding_statement(
    filters: RetrievalFilter,
) -> Select[tuple[DocumentChunkRecord, EmbeddingRecord]]:
    statement = select(DocumentChunkRecord, EmbeddingRecord).join(
        EmbeddingRecord,
        EmbeddingRecord.chunk_id == DocumentChunkRecord.chunk_id,
    )
    if filters.document_ids:
        statement = statement.where(
            DocumentChunkRecord.document_id.in_(filters.document_ids)
        )
    if filters.filenames:
        statement = statement.where(
            DocumentChunkRecord.source_filename.in_(filters.filenames)
        )
    if filters.owner_user_ids:
        statement = statement.where(
            DocumentChunkRecord.owner_user_id.in_(filters.owner_user_ids)
        )
    return statement
