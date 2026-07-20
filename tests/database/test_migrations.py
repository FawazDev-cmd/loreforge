import pytest

from loreforge.database import run_migrations
from loreforge.settings import DatabaseSettings


def test_run_migrations_requires_existing_migrations_path() -> None:
    settings = DatabaseSettings(
        url="postgresql://user:pass@localhost:5432/loreforge",
        migrations_path="missing-migrations-directory",
    )

    with pytest.raises(ValueError, match="migrations path"):
        run_migrations(settings)
