from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from loreforge.catalog import CatalogEntry, DocumentStatus
from loreforge.database import (
    SqlAlchemyCatalogRepository,
    SqlAlchemyChunkRepository,
    SqlAlchemyEmbeddingRepository,
    SqlAlchemyRetrievalRepository,
)
from loreforge.database.base import Base
from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.embeddings import EmbeddingVector
from loreforge.embeddings.pipeline import EmbeddedChunk
from loreforge.retrieval import (
    LEXICAL_STRATEGY,
    SEMANTIC_STRATEGY,
    HybridSearchRequest,
    RetrievalFilter,
    durable_hybrid_search,
)

DOC1 = UUID("00000000-0000-0000-0000-000000000001")
DOC2 = UUID("00000000-0000-0000-0000-000000000002")
CHUNK1 = UUID("00000000-0000-0000-0000-000000000101")
CHUNK2 = UUID("00000000-0000-0000-0000-000000000102")
CHUNK3 = UUID("00000000-0000-0000-0000-000000000103")
UPLOADED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
QUESTION = "refund policy"


class FakeQueryEmbeddingProvider:
    def __init__(self) -> None:
        self.questions: list[str] = []

    def embed_query(self, question: str) -> EmbeddingVector:
        self.questions.append(question)
        return EmbeddingVector(item_id=CHUNK1, values=(1.0, 0.0))


def test_durable_hybrid_search_merges_and_deduplicates_results() -> None:
    engine = _engine()
    try:
        retrieval = _populate(engine)
        provider = FakeQueryEmbeddingProvider()

        response = durable_hybrid_search(
            request=HybridSearchRequest(
                question=QUESTION,
                top_k=3,
                semantic_top_k=3,
                lexical_top_k=3,
            ),
            semantic_provider=provider,
            repository=retrieval,
        )

        assert provider.questions == [QUESTION]
        assert response.question == QUESTION
        chunk_ids = [result.chunk.chunk_id for result in response.results]
        assert chunk_ids == [CHUNK1, CHUNK3, CHUNK2]
        assert len(chunk_ids) == len(set(chunk_ids))
        assert response.results[0].contributions[0].strategy == SEMANTIC_STRATEGY
        assert response.results[0].contributions[1].strategy == LEXICAL_STRATEGY
    finally:
        engine.dispose()


def test_durable_hybrid_search_applies_metadata_filtering() -> None:
    engine = _engine()
    try:
        retrieval = _populate(engine)
        response = durable_hybrid_search(
            request=HybridSearchRequest(
                question=QUESTION,
                top_k=3,
                semantic_top_k=3,
                lexical_top_k=3,
            ),
            semantic_provider=FakeQueryEmbeddingProvider(),
            repository=retrieval,
            filters=RetrievalFilter(document_ids=(DOC2,)),
        )

        assert [result.chunk.chunk_id for result in response.results] == [CHUNK3]
        strategies = tuple(
            contribution.strategy for contribution in response.results[0].contributions
        )
        assert strategies == (SEMANTIC_STRATEGY, LEXICAL_STRATEGY)
    finally:
        engine.dispose()


def test_durable_hybrid_search_can_return_lexical_only_results() -> None:
    engine = _engine()
    try:
        retrieval = _populate(engine)
        response = durable_hybrid_search(
            request=HybridSearchRequest(
                question="payroll holidays",
                top_k=3,
                semantic_top_k=1,
                lexical_top_k=3,
            ),
            semantic_provider=FakeQueryEmbeddingProvider(),
            repository=retrieval,
        )

        result_by_chunk_id = {
            result.chunk.chunk_id: result for result in response.results
        }
        payroll_result = result_by_chunk_id[CHUNK2]
        assert tuple(
            contribution.strategy for contribution in payroll_result.contributions
        ) == (LEXICAL_STRATEGY,)
    finally:
        engine.dispose()


def _engine() -> Engine:
    database_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(database_engine)
    return database_engine


def _populate(engine: Engine) -> SqlAlchemyRetrievalRepository:
    session_factory: sessionmaker[Session] = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    catalog = SqlAlchemyCatalogRepository(session_factory)
    for document_id in (DOC1, DOC2):
        catalog.add(
            CatalogEntry(
                document_id=document_id,
                filename=f"{document_id}.pdf",
                uploaded_at=UPLOADED_AT,
                page_count=1,
                chunk_count=0,
                status=DocumentStatus.UPLOADED,
            )
        )
    chunks = (
        _chunk(CHUNK1, DOC1, filename="policy.pdf", text="refund policy returns"),
        _chunk(CHUNK2, DOC1, filename="policy.pdf", text="payroll holidays"),
        _chunk(CHUNK3, DOC2, filename="guide.pdf", text="refund guide policy"),
    )
    chunk_repository = SqlAlchemyChunkRepository(session_factory)
    chunk_repository.add(chunks)
    embedding_repository = SqlAlchemyEmbeddingRepository(session_factory)
    embedding_repository.add(
        (
            _embedded(chunks[0], (1.0, 0.0)),
            _embedded(chunks[1], (0.0, 1.0)),
            _embedded(chunks[2], (0.8, 0.2)),
        )
    )
    return SqlAlchemyRetrievalRepository(
        chunk_repository=chunk_repository,
        embedding_repository=embedding_repository,
    )


def _chunk(
    chunk_id: UUID,
    document_id: UUID,
    *,
    filename: str,
    text: str,
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        source=DocumentSource(
            filename=filename,
            media_type="application/pdf",
            size_bytes=100,
        ),
        page_number=1,
        chunk_index=0,
        text=text,
    )


def _embedded(chunk: DocumentChunk, values: tuple[float, ...]) -> EmbeddedChunk:
    return EmbeddedChunk(
        chunk=chunk,
        vector=EmbeddingVector(item_id=chunk.chunk_id, values=values),
    )
