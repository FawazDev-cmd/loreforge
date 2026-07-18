from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from loreforge.application import create_application_container
from loreforge.settings import (
    AuthProvider,
    LogLevel,
    ProviderSelection,
    RuntimeEnvironment,
    SettingsError,
    StorageProvider,
    load_settings,
)


def test_settings_load_safe_defaults() -> None:
    settings = load_settings({})

    assert settings.application.environment is RuntimeEnvironment.DEVELOPMENT
    assert settings.application.service_name == "loreforge"
    assert settings.api.host == "127.0.0.1"
    assert settings.api.port == 8000
    assert settings.logging.level is LogLevel.INFO
    assert settings.providers.document_embeddings is ProviderSelection.DISABLED
    assert settings.providers.query_embeddings is ProviderSelection.DISABLED
    assert settings.providers.reranker is ProviderSelection.DISABLED
    assert settings.providers.llm is ProviderSelection.DISABLED
    assert settings.database.url is None
    assert settings.storage.provider is StorageProvider.LOCAL
    assert settings.auth.provider is AuthProvider.DISABLED


def test_settings_loads_environment_selection_and_grouped_values() -> None:
    settings = load_settings(
        {
            "LOREFORGE_ENVIRONMENT": "testing",
            "LOREFORGE_API_HOST": "0.0.0.0",
            "LOREFORGE_API_PORT": "8080",
            "LOREFORGE_CORS_ALLOWED_ORIGINS": (
                "https://app.example.test, http://localhost:3000"
            ),
            "LOREFORGE_LOG_LEVEL": "debug",
            "LOREFORGE_STRUCTURED_LOGGING": "true",
            "LOREFORGE_REQUEST_LOGGING_ENABLED": "false",
            "LOREFORGE_STORAGE_LOCAL_PATH": ".tmp/loreforge",
            "LOREFORGE_METRICS_ENABLED": "false",
        }
    )

    assert settings.application.environment is RuntimeEnvironment.TESTING
    assert settings.api.host == "0.0.0.0"
    assert settings.api.port == 8080
    assert settings.api.cors_allowed_origins == (
        "https://app.example.test",
        "http://localhost:3000",
    )
    assert settings.logging.level is LogLevel.DEBUG
    assert settings.logging.structured is True
    assert settings.logging.request_logging_enabled is False
    assert settings.storage.local_path == Path(".tmp/loreforge")
    assert settings.observability.metrics_enabled is False


def test_settings_models_are_immutable() -> None:
    settings = load_settings({})

    with pytest.raises(FrozenInstanceError):
        settings.application.service_name = "changed"


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(SettingsError, match="LOREFORGE_ENVIRONMENT"):
        load_settings({"LOREFORGE_ENVIRONMENT": "staging"})


def test_malformed_numeric_configuration_is_rejected() -> None:
    with pytest.raises(SettingsError, match="LOREFORGE_API_PORT"):
        load_settings({"LOREFORGE_API_PORT": "not-a-number"})


def test_invalid_url_configuration_is_rejected() -> None:
    with pytest.raises(SettingsError, match="LOREFORGE_OPENROUTER_BASE_URL"):
        load_settings({"LOREFORGE_OPENROUTER_BASE_URL": "http://example.test"})


def test_provider_configuration_remains_disabled_by_default() -> None:
    settings = load_settings({})

    assert settings.providers.gemini.api_key is None
    assert settings.providers.openrouter.api_key is None
    assert settings.providers.llm is ProviderSelection.DISABLED


def test_openrouter_llm_requires_secret_and_model_when_enabled() -> None:
    with pytest.raises(SettingsError, match="LOREFORGE_OPENROUTER_API_KEY"):
        load_settings({"LOREFORGE_LLM_PROVIDER": "openrouter"})

    with pytest.raises(SettingsError, match="LOREFORGE_OPENROUTER_MODEL"):
        load_settings(
            {
                "LOREFORGE_LLM_PROVIDER": "openrouter",
                "LOREFORGE_OPENROUTER_API_KEY": "placeholder-key",
            }
        )


def test_gemini_embeddings_require_secret_and_model_when_enabled() -> None:
    with pytest.raises(SettingsError, match="LOREFORGE_GEMINI_API_KEY"):
        load_settings({"LOREFORGE_QUERY_EMBEDDINGS_PROVIDER": "gemini"})

    with pytest.raises(SettingsError, match="LOREFORGE_GEMINI_EMBEDDING_MODEL"):
        load_settings(
            {
                "LOREFORGE_QUERY_EMBEDDINGS_PROVIDER": "gemini",
                "LOREFORGE_GEMINI_API_KEY": "placeholder-key",
            }
        )


def test_supabase_storage_requires_all_storage_settings_when_enabled() -> None:
    with pytest.raises(SettingsError, match="LOREFORGE_SUPABASE_URL"):
        load_settings({"LOREFORGE_STORAGE_PROVIDER": "supabase"})

    with pytest.raises(SettingsError, match="LOREFORGE_SUPABASE_STORAGE_BUCKET"):
        load_settings(
            {
                "LOREFORGE_STORAGE_PROVIDER": "supabase",
                "LOREFORGE_SUPABASE_URL": "https://project.example.test",
            }
        )

    with pytest.raises(SettingsError, match="LOREFORGE_SUPABASE_SERVICE_ROLE_KEY"):
        load_settings(
            {
                "LOREFORGE_STORAGE_PROVIDER": "supabase",
                "LOREFORGE_SUPABASE_URL": "https://project.example.test",
                "LOREFORGE_SUPABASE_STORAGE_BUCKET": "documents",
            }
        )


def test_supabase_auth_requires_jwt_settings_when_enabled() -> None:
    with pytest.raises(SettingsError, match="LOREFORGE_AUTH_JWT_ISSUER"):
        load_settings({"LOREFORGE_AUTH_PROVIDER": "supabase"})

    with pytest.raises(SettingsError, match="LOREFORGE_AUTH_JWT_AUDIENCE"):
        load_settings(
            {
                "LOREFORGE_AUTH_PROVIDER": "supabase",
                "LOREFORGE_AUTH_JWT_ISSUER": "https://issuer.example.test",
            }
        )

    with pytest.raises(SettingsError, match="LOREFORGE_AUTH_JWKS_URL"):
        load_settings(
            {
                "LOREFORGE_AUTH_PROVIDER": "supabase",
                "LOREFORGE_AUTH_JWT_ISSUER": "https://issuer.example.test",
                "LOREFORGE_AUTH_JWT_AUDIENCE": "authenticated",
            }
        )


def test_production_environment_requires_public_base_url() -> None:
    with pytest.raises(SettingsError, match="LOREFORGE_PUBLIC_BASE_URL"):
        load_settings({"LOREFORGE_ENVIRONMENT": "production"})


def test_application_container_stores_validated_settings() -> None:
    settings = load_settings({"LOREFORGE_ENVIRONMENT": "testing"})

    container = create_application_container(settings=settings)

    assert container.settings is settings
