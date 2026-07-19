from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import UUID

import pytest
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
    ChunkRepository,
    EmbeddingRepository,
    LexicalSearchRequest,
    RetrievalFilter,
    RetrievalRepository,
    RetrievalRepositoryError,
)

DOC1 = UUID("00000000-0000-0000-0000-000000000001")
DOC2 = UUID("00000000-0000-0000-0000-000000000002")
CHUNK1 = UUID("00000000-0000-0000-0000-000000000101")
CHUNK2 = UUID("00000000-0000-0000-0000-000000000102")
CHUNK3 = UUID("00000000-0000-0000-0000-000000000103")
UPLOADED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def engine() -> Iterator[Engine]:
    database_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(database_engine)
    try:
        yield database_engine
    finally:
        database_engine.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_sqlalchemy_retrieval_repositories_satisfy_protocols(
    session_factory: sessionmaker[Session],
) -> None:
    chunks = SqlAlchemyChunkRepository(session_factory)
    embeddings = SqlAlchemyEmbeddingRepository(session_factory)
    retrieval = SqlAlchemyRetrievalRepository(
        chunk_repository=chunks,
        embedding_repository=embeddings,
    )

    assert isinstance(chunks, ChunkRepository)
    assert isinstance(embeddings, EmbeddingRepository)
    assert isinstance(retrieval, RetrievalRepository)


def test_chunk_repository_crud_ordering_and_filters(
    session_factory: sessionmaker[Session],
) -> None:
    _add_documents(session_factory)
    repository = SqlAlchemyChunkRepository(session_factory)
    first = _chunk(CHUNK1, DOC1, text="alpha refund policy")
    second = _chunk(CHUNK2, DOC2, filename="handbook.pdf", text="beta payroll guide")

    repository.add((first, second))

    assert repository.get(CHUNK1) == first
    assert repository.list() == (first, second)
    assert repository.list_for_document(DOC2) == (second,)
    assert repository.list(RetrievalFilter(filenames=("policy.pdf",))) == (first,)
    assert repository.remove(CHUNK1) is True
    assert repository.remove(CHUNK1) is False
    assert repository.list() == (second,)


def test_chunk_repository_rejects_duplicate_chunk_id(
    session_factory: sessionmaker[Session],
) -> None:
    _add_documents(session_factory)
    repository = SqlAlchemyChunkRepository(session_factory)
    repository.add((_chunk(CHUNK1, DOC1),))

    with pytest.raises(RetrievalRepositoryError, match="chunk_id"):
        repository.add((_chunk(CHUNK1, DOC1, text="duplicate text"),))


def test_embedding_repository_crud_ordering_and_filters(
    session_factory: sessionmaker[Session],
) -> None:
    _add_documents(session_factory)
    chunk_repository = SqlAlchemyChunkRepository(session_factory)
    chunks = (
        _chunk(CHUNK1, DOC1, text="alpha refund policy"),
        _chunk(CHUNK2, DOC2, filename="handbook.pdf", text="beta payroll guide"),
    )
    chunk_repository.add(chunks)
    repository = SqlAlchemyEmbeddingRepository(session_factory)
    embedded = (_embedded(chunks[0], (1.0, 0.0)), _embedded(chunks[1], (0.0, 1.0)))

    repository.add(embedded)

    assert repository.get(CHUNK1) == embedded[0]
    assert repository.list() == embedded
    assert repository.list_for_document(DOC2) == (embedded[1],)
    assert repository.list(RetrievalFilter(document_ids=(DOC1,))) == (embedded[0],)
    assert repository.remove(CHUNK1) is True
    assert repository.remove(CHUNK1) is False
    assert repository.list() == (embedded[1],)


def test_embedding_repository_rejects_duplicate_chunk_id(
    session_factory: sessionmaker[Session],
) -> None:
    _add_documents(session_factory)
    chunk_repository = SqlAlchemyChunkRepository(session_factory)
    chunk = _chunk(CHUNK1, DOC1)
    chunk_repository.add((chunk,))
    repository = SqlAlchemyEmbeddingRepository(session_factory)
    repository.add((_embedded(chunk, (1.0, 0.0)),))

    with pytest.raises(RetrievalRepositoryError, match="chunk_id"):
        repository.add((_embedded(chunk, (0.5, 0.5)),))


def test_repository_backed_lexical_retrieval_ranks_and_filters(
    session_factory: sessionmaker[Session],
) -> None:
    retrieval = _populated_retrieval_repository(session_factory)

    response = retrieval.lexical_search(
        LexicalSearchRequest(query="refund policy", top_k=3)
    )

    assert [result.chunk.chunk_id for result in response.results] == [CHUNK3, CHUNK1]
    filtered = retrieval.lexical_search(
        LexicalSearchRequest(query="refund policy", top_k=3),
        filters=RetrievalFilter(filenames=("guide.pdf",)),
    )
    assert [result.chunk.chunk_id for result in filtered.results] == [CHUNK3]


def test_repository_backed_vector_retrieval_ranks_filters_and_rejects_bad_top_k(
    session_factory: sessionmaker[Session],
) -> None:
    retrieval = _populated_retrieval_repository(session_factory)

    results = retrieval.vector_search(query_vector=(1.0, 0.0), top_k=3)

    assert [result.indexed.chunk.chunk_id for result in results] == [
        CHUNK1,
        CHUNK3,
        CHUNK2,
    ]
    filtered = retrieval.vector_search(
        query_vector=(1.0, 0.0),
        top_k=3,
        filters=RetrievalFilter(document_ids=(DOC2,)),
    )
    assert [result.indexed.chunk.chunk_id for result in filtered] == [CHUNK3]
    with pytest.raises(RetrievalRepositoryError, match="top_k"):
        retrieval.vector_search(query_vector=(1.0, 0.0), top_k=0)


def test_repository_backed_retrieval_returns_empty_for_empty_filters(
    session_factory: sessionmaker[Session],
) -> None:
    retrieval = _populated_retrieval_repository(session_factory)
    filters = RetrievalFilter(filenames=("missing.pdf",))

    lexical = retrieval.lexical_search(
        LexicalSearchRequest(query="refund", top_k=3),
        filters=filters,
    )
    semantic = retrieval.vector_search(
        query_vector=(1.0, 0.0),
        top_k=3,
        filters=filters,
    )

    assert lexical.results == ()
    assert semantic == ()


def _populated_retrieval_repository(
    session_factory: sessionmaker[Session],
) -> SqlAlchemyRetrievalRepository:
    _add_documents(session_factory)
    chunk_repository = SqlAlchemyChunkRepository(session_factory)
    chunks = (
        _chunk(CHUNK1, DOC1, text="refund policy allows returns"),
        _chunk(CHUNK2, DOC1, text="payroll calendar and holidays"),
        _chunk(CHUNK3, DOC2, filename="guide.pdf", text="refund guide policy"),
    )
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


def _add_documents(session_factory: sessionmaker[Session]) -> None:
    repository = SqlAlchemyCatalogRepository(session_factory)
    for document_id in (DOC1, DOC2):
        repository.add(
            CatalogEntry(
                document_id=document_id,
                filename=f"{document_id}.pdf",
                uploaded_at=UPLOADED_AT,
                page_count=1,
                chunk_count=0,
                status=DocumentStatus.UPLOADED,
            )
        )


def _chunk(
    chunk_id: UUID,
    document_id: UUID,
    *,
    filename: str = "policy.pdf",
    text: str = "refund policy text",
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
