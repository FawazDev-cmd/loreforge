from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from uuid import UUID

from fastapi.testclient import TestClient

from loreforge.main import create_app
from loreforge.settings import LoreForgeSettings, load_settings

TEST_USER_ID = UUID("00000000-0000-0000-0000-00000000f001")
TEST_API_KEY = "test-api-key"


def default_test_settings(
    overrides: Mapping[str, str] | None = None,
) -> LoreForgeSettings:
    values = {
        "LOREFORGE_ENVIRONMENT": "testing",
        "LOREFORGE_AUTH_PROVIDER": "disabled",
        "LOREFORGE_DOCUMENT_EMBEDDINGS_PROVIDER": "disabled",
        "LOREFORGE_QUERY_EMBEDDINGS_PROVIDER": "disabled",
        "LOREFORGE_RERANKER_PROVIDER": "disabled",
        "LOREFORGE_LLM_PROVIDER": "disabled",
        "LOREFORGE_DATABASE_URL": "",
        "LOREFORGE_DATABASE_MIGRATIONS_ENABLED": "false",
        "LOREFORGE_RUN_LIVE_GEMINI_SMOKE": "false",
        "LOREFORGE_RUN_LIVE_DATABASE_SMOKE": "false",
    }
    if overrides is not None:
        values.update(overrides)
    return load_settings(values, env_file=None)


def authenticated_test_settings(
    overrides: Mapping[str, str] | None = None,
) -> LoreForgeSettings:
    values = {
        "LOREFORGE_AUTH_PROVIDER": "api_key",
        "LOREFORGE_AUTH_API_KEYS": f"{TEST_USER_ID}:{TEST_API_KEY}:Test User",
    }
    if overrides is not None:
        values.update(overrides)
    return default_test_settings(values)


def auth_headers(api_key: str = TEST_API_KEY) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


@contextmanager
def anonymous_test_client() -> Iterator[TestClient]:
    with TestClient(create_app(settings=default_test_settings())) as client:
        yield client


@contextmanager
def authenticated_test_client() -> Iterator[TestClient]:
    with TestClient(create_app(settings=authenticated_test_settings())) as client:
        yield client
