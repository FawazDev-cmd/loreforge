from collections.abc import Iterator
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from loreforge.auth import AuthRepositoryError, UserIdentity, UserRepository
from loreforge.database import SqlAlchemyUserRepository
from loreforge.database.base import Base
from loreforge.database.models import DocumentChunkRecord, DocumentRecord, UserRecord

USER1 = UUID("00000000-0000-0000-0000-000000000111")
USER2 = UUID("00000000-0000-0000-0000-000000000222")


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


def test_sqlalchemy_user_repository_crud_and_protocol(
    session_factory: sessionmaker[Session],
) -> None:
    repository = SqlAlchemyUserRepository(session_factory)
    user = UserIdentity(user_id=USER1, display_name="Owner One")

    repository.add(user)

    assert isinstance(repository, UserRepository)
    assert repository.get(USER1) == user
    assert repository.list() == (user,)
    assert repository.get(USER2) is None


def test_sqlalchemy_user_repository_rejects_duplicates(
    session_factory: sessionmaker[Session],
) -> None:
    repository = SqlAlchemyUserRepository(session_factory)
    repository.add(UserIdentity(user_id=USER1))

    with pytest.raises(AuthRepositoryError, match="user_id"):
        repository.add(UserIdentity(user_id=USER1, display_name="Duplicate"))


def test_ownership_columns_exist_in_metadata() -> None:
    assert UserRecord.__tablename__ == "users"
    assert DocumentRecord.__table__.columns["owner_user_id"].nullable is True
    assert DocumentChunkRecord.__table__.columns["owner_user_id"].nullable is True
