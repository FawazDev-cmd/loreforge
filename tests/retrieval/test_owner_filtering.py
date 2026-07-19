from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from loreforge.auth import UserIdentity
from loreforge.catalog import CatalogEntry, DocumentStatus
from loreforge.database import (
    SqlAlchemyCatalogRepository,
    SqlAlchemyChunkRepository,
    SqlAlchemyEmbeddingRepository,
    SqlAlchemyRetrievalRepository,
    SqlAlchemyUserRepository,
)
from loreforge.database.base import Base
from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.embeddings import EmbeddingVector
from loreforge.embeddings.pipeline import EmbeddedChunk
from loreforge.retrieval import LexicalSearchRequest, RetrievalFilter

DOC1 = UUID("00000000-0000-0000-0000-000000000001")
DOC2 = UUID("00000000-0000-0000-0000-000000000002")
CHUNK1 = UUID("00000000-0000-0000-0000-000000000101")
CHUNK2 = UUID("00000000-0000-0000-0000-000000000102")
USER1 = UUID("00000000-0000-0000-0000-000000000111")
USER2 = UUID("00000000-0000-0000-0000-000000000222")
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


def test_durable_retrieval_filters_by_owner_at_repository_boundary(
    session_factory: sessionmaker[Session],
) -> None:
    _populate(session_factory)
    chunk_repository = SqlAlchemyChunkRepository(session_factory)
    embedding_repository = SqlAlchemyEmbeddingRepository(session_factory)
    retrieval = SqlAlchemyRetrievalRepository(
        chunk_repository=chunk_repository,
        embedding_repository=embedding_repository,
    )

    owner_one_filter = RetrievalFilter(owner_user_ids=(USER1,))
    owner_two_filter = RetrievalFilter(owner_user_ids=(USER2,))

    assert [chunk.chunk_id for chunk in chunk_repository.list(owner_one_filter)] == [
        CHUNK1
    ]
    assert [chunk.chunk_id for chunk in chunk_repository.list(owner_two_filter)] == [
        CHUNK2
    ]
    assert [
        result.chunk.chunk_id
        for result in retrieval.lexical_search(
            LexicalSearchRequest(query="refund policy", top_k=5),
            filters=owner_one_filter,
        ).results
    ] == [CHUNK1]
    assert [
        result.indexed.chunk.chunk_id
        for result in retrieval.vector_search(
            query_vector=(1.0, 0.0),
            top_k=5,
            filters=owner_two_filter,
        )
    ] == [CHUNK2]


def _populate(session_factory: sessionmaker[Session]) -> None:
    users = SqlAlchemyUserRepository(session_factory)
    users.add(UserIdentity(user_id=USER1, display_name="Owner One"))
    users.add(UserIdentity(user_id=USER2, display_name="Owner Two"))

    catalog = SqlAlchemyCatalogRepository(session_factory)
    catalog.add(_entry(DOC1, USER1, "policy.pdf"))
    catalog.add(_entry(DOC2, USER2, "handbook.pdf"))

    chunk_repository = SqlAlchemyChunkRepository(session_factory)
    first = _chunk(CHUNK1, DOC1, "policy.pdf", "refund policy alpha")
    second = _chunk(CHUNK2, DOC2, "handbook.pdf", "refund policy beta")
    chunk_repository.add((first,), owner_user_id=USER1)
    chunk_repository.add((second,), owner_user_id=USER2)

    embedding_repository = SqlAlchemyEmbeddingRepository(session_factory)
    embedding_repository.add(
        (
            EmbeddedChunk(
                chunk=first,
                vector=EmbeddingVector(item_id=CHUNK1, values=(1.0, 0.0)),
            ),
            EmbeddedChunk(
                chunk=second,
                vector=EmbeddingVector(item_id=CHUNK2, values=(0.0, 1.0)),
            ),
        )
    )


def _entry(document_id: UUID, owner_user_id: UUID, filename: str) -> CatalogEntry:
    return CatalogEntry(
        document_id=document_id,
        filename=filename,
        uploaded_at=UPLOADED_AT,
        page_count=1,
        chunk_count=1,
        status=DocumentStatus.UPLOADED,
        owner_user_id=owner_user_id,
    )


def _chunk(
    chunk_id: UUID,
    document_id: UUID,
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
