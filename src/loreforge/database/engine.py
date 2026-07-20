"""Database engine, session, migration, and health helpers."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from loreforge.settings import DatabaseSettings

SessionFactory = Callable[[], Session]


@dataclass(frozen=True, slots=True)
class DatabaseHealth:
    """Result of a database connectivity check."""

    healthy: bool


@dataclass(frozen=True, slots=True)
class DatabaseRuntime:
    """Owned SQLAlchemy database resources for one application instance."""

    engine: Engine
    session_factory: sessionmaker[Session]

    def close(self) -> None:
        """Dispose database connections owned by this runtime."""
        self.engine.dispose()

    def check_health(self) -> DatabaseHealth:
        """Verify that the configured database accepts a simple query."""
        return check_database_health(self.session_factory)


def normalize_database_url(url: str) -> str:
    """Return a SQLAlchemy URL that uses the psycopg PostgreSQL driver."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def create_sqlalchemy_engine(settings: DatabaseSettings) -> Engine:
    """Create a SQLAlchemy engine from validated database settings."""
    if settings.url is None:
        msg = "database URL is required"
        raise ValueError(msg)
    pool_size = max(settings.pool_min_size, 1)
    max_overflow = max(settings.pool_max_size - pool_size, 0)
    return create_engine(
        normalize_database_url(settings.url),
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
    )


def create_database_runtime(settings: DatabaseSettings) -> DatabaseRuntime | None:
    """Create database runtime resources when a database URL is configured."""
    if settings.url is None:
        return None
    engine = create_sqlalchemy_engine(settings)
    runtime = DatabaseRuntime(
        engine=engine,
        session_factory=sessionmaker(bind=engine, expire_on_commit=False),
    )
    if settings.migrations_enabled:
        run_migrations(settings)
    return runtime


def run_migrations(settings: DatabaseSettings) -> None:
    """Run Alembic migrations for the configured database."""
    if settings.url is None:
        msg = "database URL is required to run migrations"
        raise ValueError(msg)
    if not migrations_path_exists(settings):
        msg = "database migrations path does not exist"
        raise ValueError(msg)
    config = Config("alembic.ini")
    config.set_main_option("script_location", settings.migrations_path)
    config.set_main_option("sqlalchemy.url", normalize_database_url(settings.url))
    command.upgrade(config, "head")


def check_database_health(session_factory: SessionFactory) -> DatabaseHealth:
    """Return healthy when the database accepts a simple SELECT."""
    with session_factory() as session:
        session.execute(text("SELECT 1"))
    return DatabaseHealth(healthy=True)


def migrations_path_exists(settings: DatabaseSettings) -> bool:
    """Return whether the configured migration script path exists."""
    return Path(settings.migrations_path).exists()
