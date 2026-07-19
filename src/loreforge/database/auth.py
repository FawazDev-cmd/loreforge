"""SQLAlchemy authentication repository adapters."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from loreforge.auth import AuthRepositoryError, UserIdentity
from loreforge.database.engine import SessionFactory
from loreforge.database.models import UserRecord


class SqlAlchemyUserRepository:
    """Durable user repository backed by SQLAlchemy sessions."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(self, user: UserIdentity) -> None:
        record = UserRecord(user_id=user.user_id, display_name=user.display_name)
        try:
            with self._session_factory() as session, session.begin():
                session.add(record)
        except IntegrityError as exc:
            msg = "user_id already exists"
            raise AuthRepositoryError(msg) from exc

    def get(self, user_id: UUID) -> UserIdentity | None:
        with self._session_factory() as session:
            record = session.scalar(
                select(UserRecord).where(UserRecord.user_id == user_id)
            )
            if record is None:
                return None
            return _user_from_record(record)

    def list(self) -> tuple[UserIdentity, ...]:
        statement = select(UserRecord).order_by(UserRecord.row_id)
        with self._session_factory() as session:
            return tuple(
                _user_from_record(record) for record in session.scalars(statement)
            )


def _user_from_record(record: UserRecord) -> UserIdentity:
    return UserIdentity(user_id=record.user_id, display_name=record.display_name)
