"""Centralized runtime settings for LoreForge."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from pathlib import Path
from typing import TypeVar
from urllib.parse import urlparse

_SettingsEnum = TypeVar("_SettingsEnum", bound=StrEnum)


class SettingsError(ValueError):
    """Raised when runtime settings are invalid."""


class RuntimeEnvironment(StrEnum):
    """Supported application runtime environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Supported application log levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ProviderSelection(StrEnum):
    """Provider selection modes prepared for runtime composition."""

    DISABLED = "disabled"
    LOCAL = "local"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"


class StorageProvider(StrEnum):
    """Storage provider selection modes."""

    LOCAL = "local"
    SUPABASE = "supabase"


class AuthProvider(StrEnum):
    """Authentication provider selection modes."""

    DISABLED = "disabled"
    SUPABASE = "supabase"


@dataclass(frozen=True, slots=True)
class ApplicationSettings:
    """Application identity and environment settings."""

    environment: RuntimeEnvironment = RuntimeEnvironment.DEVELOPMENT
    service_name: str = "loreforge"
    api_title: str = "LoreForge"
    api_version: str = "0.1.0"
    public_base_url: str | None = None

    def __post_init__(self) -> None:
        _require_nonblank(self.service_name, "LOREFORGE_SERVICE_NAME")
        _require_nonblank(self.api_title, "LOREFORGE_API_TITLE")
        _require_nonblank(self.api_version, "LOREFORGE_API_VERSION")
        if self.public_base_url is not None:
            _require_https_url(self.public_base_url, "LOREFORGE_PUBLIC_BASE_URL")


@dataclass(frozen=True, slots=True)
class ApiSettings:
    """HTTP runtime settings for the API process."""

    host: str = "127.0.0.1"
    port: int = 8000
    cors_allowed_origins: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_nonblank(self.host, "LOREFORGE_API_HOST")
        _require_port(self.port, "LOREFORGE_API_PORT")
        for origin in self.cors_allowed_origins:
            _require_http_url(origin, "LOREFORGE_CORS_ALLOWED_ORIGINS")


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    """Logging controls used by the application runtime."""

    level: LogLevel = LogLevel.INFO
    structured: bool = False
    request_logging_enabled: bool = True


@dataclass(frozen=True, slots=True)
class GeminiSettings:
    """Gemini provider settings for embedding and generation adapters."""

    api_key: str | None = None
    generation_model: str | None = None
    embedding_model: str | None = None
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        _require_positive_float(
            self.timeout_seconds,
            "LOREFORGE_GEMINI_TIMEOUT_SECONDS",
        )
        _validate_optional_secret(self.api_key, "LOREFORGE_GEMINI_API_KEY")
        _validate_optional_nonblank(
            self.generation_model,
            "LOREFORGE_GEMINI_GENERATION_MODEL",
        )
        _validate_optional_nonblank(
            self.embedding_model,
            "LOREFORGE_GEMINI_EMBEDDING_MODEL",
        )


@dataclass(frozen=True, slots=True)
class OpenRouterSettings:
    """OpenRouter provider settings prepared for runtime injection."""

    api_key: str | None = None
    model: str | None = None
    base_url: str = "https://openrouter.ai/api/v1"
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        _validate_optional_secret(self.api_key, "LOREFORGE_OPENROUTER_API_KEY")
        _validate_optional_nonblank(self.model, "LOREFORGE_OPENROUTER_MODEL")
        _require_https_url(self.base_url, "LOREFORGE_OPENROUTER_BASE_URL")
        _require_positive_float(
            self.timeout_seconds,
            "LOREFORGE_OPENROUTER_TIMEOUT_SECONDS",
        )


@dataclass(frozen=True, slots=True)
class LocalProviderSettings:
    """Local model settings for development-only provider paths."""

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    batch_size: int = 32

    def __post_init__(self) -> None:
        _require_nonblank(
            self.embedding_model,
            "LOREFORGE_LOCAL_EMBEDDING_MODEL",
        )
        _require_nonblank(self.reranker_model, "LOREFORGE_LOCAL_RERANKER_MODEL")
        _require_positive_int(self.batch_size, "LOREFORGE_LOCAL_BATCH_SIZE")


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    """Provider selection and provider-specific runtime settings."""

    document_embeddings: ProviderSelection = ProviderSelection.DISABLED
    query_embeddings: ProviderSelection = ProviderSelection.DISABLED
    reranker: ProviderSelection = ProviderSelection.DISABLED
    llm: ProviderSelection = ProviderSelection.DISABLED
    gemini: GeminiSettings = field(default_factory=GeminiSettings)
    openrouter: OpenRouterSettings = field(default_factory=OpenRouterSettings)
    local: LocalProviderSettings = field(default_factory=LocalProviderSettings)

    def __post_init__(self) -> None:
        supported_embedding_providers = (
            ProviderSelection.DISABLED,
            ProviderSelection.LOCAL,
            ProviderSelection.GEMINI,
        )
        if self.document_embeddings not in supported_embedding_providers:
            msg = (
                "LOREFORGE_DOCUMENT_EMBEDDINGS_PROVIDER must be disabled, "
                "local, or gemini"
            )
            raise SettingsError(msg)
        if self.query_embeddings not in supported_embedding_providers:
            msg = (
                "LOREFORGE_QUERY_EMBEDDINGS_PROVIDER must be disabled, local, or gemini"
            )
            raise SettingsError(msg)
        if self.reranker not in (ProviderSelection.DISABLED, ProviderSelection.LOCAL):
            msg = (
                "LOREFORGE_RERANKER_PROVIDER must be disabled or local "
                "until another reranker adapter exists"
            )
            raise SettingsError(msg)
        if self.llm not in (
            ProviderSelection.DISABLED,
            ProviderSelection.GEMINI,
            ProviderSelection.OPENROUTER,
        ):
            msg = "LOREFORGE_LLM_PROVIDER must be disabled, gemini, or openrouter"
            raise SettingsError(msg)

        if self.llm == ProviderSelection.GEMINI:
            if self.gemini.api_key is None:
                msg = "LOREFORGE_GEMINI_API_KEY is required when Gemini LLM is enabled"
                raise SettingsError(msg)
            if self.gemini.generation_model is None:
                msg = (
                    "LOREFORGE_GEMINI_GENERATION_MODEL is required when "
                    "Gemini LLM is enabled"
                )
                raise SettingsError(msg)

        if (
            self.document_embeddings == ProviderSelection.GEMINI
            or self.query_embeddings == ProviderSelection.GEMINI
        ):
            if self.gemini.api_key is None:
                msg = (
                    "LOREFORGE_GEMINI_API_KEY is required when Gemini embeddings "
                    "are enabled"
                )
                raise SettingsError(msg)
            if self.gemini.embedding_model is None:
                msg = (
                    "LOREFORGE_GEMINI_EMBEDDING_MODEL is required when Gemini "
                    "embeddings are enabled"
                )
                raise SettingsError(msg)

        if self.llm == ProviderSelection.OPENROUTER:
            if self.openrouter.api_key is None:
                msg = (
                    "LOREFORGE_OPENROUTER_API_KEY is required when OpenRouter LLM "
                    "is enabled"
                )
                raise SettingsError(msg)
            if self.openrouter.model is None:
                msg = (
                    "LOREFORGE_OPENROUTER_MODEL is required when OpenRouter LLM "
                    "is enabled"
                )
                raise SettingsError(msg)


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Database settings prepared for future PostgreSQL persistence."""

    url: str | None = None
    pool_min_size: int = 1
    pool_max_size: int = 5
    migrations_enabled: bool = False
    migrations_path: str = "migrations"

    def __post_init__(self) -> None:
        if self.url is not None:
            _require_postgresql_url(self.url, "LOREFORGE_DATABASE_URL")
        _require_non_negative_int(
            self.pool_min_size,
            "LOREFORGE_DATABASE_POOL_MIN_SIZE",
        )
        _require_positive_int(
            self.pool_max_size,
            "LOREFORGE_DATABASE_POOL_MAX_SIZE",
        )
        if self.pool_min_size > self.pool_max_size:
            msg = (
                "LOREFORGE_DATABASE_POOL_MIN_SIZE must be less than or equal to "
                "LOREFORGE_DATABASE_POOL_MAX_SIZE"
            )
            raise SettingsError(msg)
        _require_nonblank(self.migrations_path, "LOREFORGE_DATABASE_MIGRATIONS_PATH")


@dataclass(frozen=True, slots=True)
class StorageSettings:
    """Storage settings prepared for local and Supabase-backed document storage."""

    provider: StorageProvider = StorageProvider.LOCAL
    local_path: Path = Path(".loreforge/storage")
    supabase_url: str | None = None
    supabase_bucket: str | None = None
    supabase_service_role_key: str | None = None

    def __post_init__(self) -> None:
        if not str(self.local_path).strip():
            msg = "LOREFORGE_STORAGE_LOCAL_PATH must not be empty"
            raise SettingsError(msg)
        if self.supabase_url is not None:
            _require_https_url(self.supabase_url, "LOREFORGE_SUPABASE_URL")
        _validate_optional_nonblank(
            self.supabase_bucket,
            "LOREFORGE_SUPABASE_STORAGE_BUCKET",
        )
        _validate_optional_secret(
            self.supabase_service_role_key,
            "LOREFORGE_SUPABASE_SERVICE_ROLE_KEY",
        )
        if self.provider == StorageProvider.SUPABASE:
            if self.supabase_url is None:
                msg = (
                    "LOREFORGE_SUPABASE_URL is required when Supabase storage "
                    "is enabled"
                )
                raise SettingsError(msg)
            if self.supabase_bucket is None:
                msg = (
                    "LOREFORGE_SUPABASE_STORAGE_BUCKET is required when Supabase "
                    "storage is enabled"
                )
                raise SettingsError(msg)
            if self.supabase_service_role_key is None:
                msg = (
                    "LOREFORGE_SUPABASE_SERVICE_ROLE_KEY is required when Supabase "
                    "storage is enabled"
                )
                raise SettingsError(msg)


@dataclass(frozen=True, slots=True)
class AuthSettings:
    """Authentication settings prepared for future Supabase JWT validation."""

    provider: AuthProvider = AuthProvider.DISABLED
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwks_url: str | None = None

    def __post_init__(self) -> None:
        if self.jwt_issuer is not None:
            _require_https_url(self.jwt_issuer, "LOREFORGE_AUTH_JWT_ISSUER")
        _validate_optional_nonblank(
            self.jwt_audience,
            "LOREFORGE_AUTH_JWT_AUDIENCE",
        )
        if self.jwks_url is not None:
            _require_https_url(self.jwks_url, "LOREFORGE_AUTH_JWKS_URL")
        if self.provider == AuthProvider.SUPABASE:
            if self.jwt_issuer is None:
                msg = (
                    "LOREFORGE_AUTH_JWT_ISSUER is required when Supabase auth "
                    "is enabled"
                )
                raise SettingsError(msg)
            if self.jwt_audience is None:
                msg = (
                    "LOREFORGE_AUTH_JWT_AUDIENCE is required when Supabase auth "
                    "is enabled"
                )
                raise SettingsError(msg)
            if self.jwks_url is None:
                msg = (
                    "LOREFORGE_AUTH_JWKS_URL is required when Supabase auth is enabled"
                )
                raise SettingsError(msg)


@dataclass(frozen=True, slots=True)
class ObservabilitySettings:
    """Runtime observability settings."""

    metrics_enabled: bool = True
    record_query_observations: bool = True


@dataclass(frozen=True, slots=True)
class LoreForgeSettings:
    """Complete typed runtime configuration for LoreForge."""

    application: ApplicationSettings = field(default_factory=ApplicationSettings)
    api: ApiSettings = field(default_factory=ApiSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    providers: ProviderSettings = field(default_factory=ProviderSettings)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    auth: AuthSettings = field(default_factory=AuthSettings)
    observability: ObservabilitySettings = field(default_factory=ObservabilitySettings)

    def __post_init__(self) -> None:
        if self.application.environment == RuntimeEnvironment.PRODUCTION:
            if self.application.public_base_url is None:
                msg = "LOREFORGE_PUBLIC_BASE_URL is required in production environment"
                raise SettingsError(msg)


def load_settings(
    environ: Mapping[str, str] | None = None,
    *,
    env_file: Path | str | None = ".env",
) -> LoreForgeSettings:
    """Load strongly typed settings from an environment mapping and optional file."""
    values = _settings_values(environ=environ, env_file=env_file)
    return LoreForgeSettings(
        application=ApplicationSettings(
            environment=_enum(
                values,
                "LOREFORGE_ENVIRONMENT",
                RuntimeEnvironment,
                RuntimeEnvironment.DEVELOPMENT,
            ),
            service_name=_string(values, "LOREFORGE_SERVICE_NAME", "loreforge"),
            api_title=_string(values, "LOREFORGE_API_TITLE", "LoreForge"),
            api_version=_string(values, "LOREFORGE_API_VERSION", "0.1.0"),
            public_base_url=_optional_string(values, "LOREFORGE_PUBLIC_BASE_URL"),
        ),
        api=ApiSettings(
            host=_string(values, "LOREFORGE_API_HOST", "127.0.0.1"),
            port=_int(values, "LOREFORGE_API_PORT", 8000),
            cors_allowed_origins=_csv(values, "LOREFORGE_CORS_ALLOWED_ORIGINS"),
        ),
        logging=LoggingSettings(
            level=_enum(values, "LOREFORGE_LOG_LEVEL", LogLevel, LogLevel.INFO),
            structured=_bool(values, "LOREFORGE_STRUCTURED_LOGGING", False),
            request_logging_enabled=_bool(
                values,
                "LOREFORGE_REQUEST_LOGGING_ENABLED",
                True,
            ),
        ),
        providers=ProviderSettings(
            document_embeddings=_enum(
                values,
                "LOREFORGE_DOCUMENT_EMBEDDINGS_PROVIDER",
                ProviderSelection,
                ProviderSelection.DISABLED,
            ),
            query_embeddings=_enum(
                values,
                "LOREFORGE_QUERY_EMBEDDINGS_PROVIDER",
                ProviderSelection,
                ProviderSelection.DISABLED,
            ),
            reranker=_enum(
                values,
                "LOREFORGE_RERANKER_PROVIDER",
                ProviderSelection,
                ProviderSelection.DISABLED,
            ),
            llm=_enum(
                values,
                "LOREFORGE_LLM_PROVIDER",
                ProviderSelection,
                ProviderSelection.DISABLED,
            ),
            gemini=GeminiSettings(
                api_key=_optional_secret(values, "LOREFORGE_GEMINI_API_KEY"),
                generation_model=_optional_string(
                    values,
                    "LOREFORGE_GEMINI_GENERATION_MODEL",
                ),
                embedding_model=_optional_string(
                    values,
                    "LOREFORGE_GEMINI_EMBEDDING_MODEL",
                ),
                timeout_seconds=_float(
                    values,
                    "LOREFORGE_GEMINI_TIMEOUT_SECONDS",
                    30.0,
                ),
            ),
            openrouter=OpenRouterSettings(
                api_key=_optional_secret(values, "LOREFORGE_OPENROUTER_API_KEY"),
                model=_optional_string(values, "LOREFORGE_OPENROUTER_MODEL"),
                base_url=_string(
                    values,
                    "LOREFORGE_OPENROUTER_BASE_URL",
                    "https://openrouter.ai/api/v1",
                ),
                timeout_seconds=_float(
                    values,
                    "LOREFORGE_OPENROUTER_TIMEOUT_SECONDS",
                    30.0,
                ),
            ),
            local=LocalProviderSettings(
                embedding_model=_string(
                    values,
                    "LOREFORGE_LOCAL_EMBEDDING_MODEL",
                    "sentence-transformers/all-MiniLM-L6-v2",
                ),
                reranker_model=_string(
                    values,
                    "LOREFORGE_LOCAL_RERANKER_MODEL",
                    "cross-encoder/ms-marco-MiniLM-L6-v2",
                ),
                batch_size=_int(values, "LOREFORGE_LOCAL_BATCH_SIZE", 32),
            ),
        ),
        database=DatabaseSettings(
            url=_optional_secret(values, "LOREFORGE_DATABASE_URL"),
            pool_min_size=_int(values, "LOREFORGE_DATABASE_POOL_MIN_SIZE", 1),
            pool_max_size=_int(values, "LOREFORGE_DATABASE_POOL_MAX_SIZE", 5),
            migrations_enabled=_bool(
                values,
                "LOREFORGE_DATABASE_MIGRATIONS_ENABLED",
                False,
            ),
            migrations_path=_string(
                values,
                "LOREFORGE_DATABASE_MIGRATIONS_PATH",
                "migrations",
            ),
        ),
        storage=StorageSettings(
            provider=_enum(
                values,
                "LOREFORGE_STORAGE_PROVIDER",
                StorageProvider,
                StorageProvider.LOCAL,
            ),
            local_path=Path(
                _string(
                    values,
                    "LOREFORGE_STORAGE_LOCAL_PATH",
                    ".loreforge/storage",
                )
            ),
            supabase_url=_optional_string(values, "LOREFORGE_SUPABASE_URL"),
            supabase_bucket=_optional_string(
                values,
                "LOREFORGE_SUPABASE_STORAGE_BUCKET",
            ),
            supabase_service_role_key=_optional_secret(
                values,
                "LOREFORGE_SUPABASE_SERVICE_ROLE_KEY",
            ),
        ),
        auth=AuthSettings(
            provider=_enum(
                values,
                "LOREFORGE_AUTH_PROVIDER",
                AuthProvider,
                AuthProvider.DISABLED,
            ),
            jwt_issuer=_optional_string(values, "LOREFORGE_AUTH_JWT_ISSUER"),
            jwt_audience=_optional_string(values, "LOREFORGE_AUTH_JWT_AUDIENCE"),
            jwks_url=_optional_string(values, "LOREFORGE_AUTH_JWKS_URL"),
        ),
        observability=ObservabilitySettings(
            metrics_enabled=_bool(values, "LOREFORGE_METRICS_ENABLED", True),
            record_query_observations=_bool(
                values,
                "LOREFORGE_RECORD_QUERY_OBSERVATIONS",
                True,
            ),
        ),
    )


def _settings_values(
    *,
    environ: Mapping[str, str] | None,
    env_file: Path | str | None,
) -> Mapping[str, str]:
    if environ is not None:
        return environ

    values = _read_env_file(env_file)
    values.update(os.environ)
    return values


def _read_env_file(env_file: Path | str | None) -> dict[str, str]:
    if env_file is None:
        return {}

    path = Path(env_file)
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            msg = f"{path} line {line_number} must use KEY=VALUE format"
            raise SettingsError(msg)
        name, raw_value = line.split("=", 1)
        name = name.strip()
        if not name:
            msg = f"{path} line {line_number} must include a variable name"
            raise SettingsError(msg)
        values[name] = _unquote_env_value(raw_value.strip())
    return values


def _unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _string(values: Mapping[str, str], name: str, default: str) -> str:
    return values.get(name, default)


def _optional_string(values: Mapping[str, str], name: str) -> str | None:
    value = values.get(name)
    if value is None:
        return None
    if not value.strip():
        return None
    return value


def _optional_secret(values: Mapping[str, str], name: str) -> str | None:
    return _optional_string(values, name)


def _int(values: Mapping[str, str], name: str, default: int) -> int:
    raw_value = values.get(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as error:
        msg = f"{name} must be an integer"
        raise SettingsError(msg) from error


def _float(values: Mapping[str, str], name: str, default: float) -> float:
    raw_value = values.get(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError as error:
        msg = f"{name} must be a number"
        raise SettingsError(msg) from error


def _bool(values: Mapping[str, str], name: str, default: bool) -> bool:
    raw_value = values.get(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    msg = f"{name} must be a boolean"
    raise SettingsError(msg)


def _csv(values: Mapping[str, str], name: str) -> tuple[str, ...]:
    raw_value = values.get(name)
    if raw_value is None or not raw_value.strip():
        return ()
    return tuple(item.strip() for item in raw_value.split(",") if item.strip())


def _enum(
    values: Mapping[str, str],
    name: str,
    enum_type: type[_SettingsEnum],
    default: _SettingsEnum,
) -> _SettingsEnum:
    raw_value = values.get(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    try:
        return enum_type(normalized)
    except ValueError as error:
        allowed = ", ".join(item.value for item in enum_type)
        msg = f"{name} must be one of: {allowed}"
        raise SettingsError(msg) from error


def _require_nonblank(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        msg = f"{name} must not be empty"
        raise SettingsError(msg)


def _validate_optional_nonblank(value: str | None, name: str) -> None:
    if value is not None:
        _require_nonblank(value, name)


def _validate_optional_secret(value: str | None, name: str) -> None:
    _validate_optional_nonblank(value, name)


def _require_positive_int(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        msg = f"{name} must be a positive integer"
        raise SettingsError(msg)


def _require_non_negative_int(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        msg = f"{name} must be a non-negative integer"
        raise SettingsError(msg)


def _require_port(value: int, name: str) -> None:
    if type(value) is not int or value < 1 or value > 65535:
        msg = f"{name} must be an integer between 1 and 65535"
        raise SettingsError(msg)


def _require_positive_float(value: float, name: str) -> None:
    if type(value) is not float or not isfinite(value) or value <= 0.0:
        msg = f"{name} must be finite and greater than zero"
        raise SettingsError(msg)


def _require_http_url(value: str, name: str) -> None:
    _require_nonblank(value, name)
    parsed_url = urlparse(value)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        msg = f"{name} must be an http or https URL"
        raise SettingsError(msg)


def _require_https_url(value: str, name: str) -> None:
    _require_nonblank(value, name)
    parsed_url = urlparse(value)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        msg = f"{name} must be an https URL"
        raise SettingsError(msg)


def _require_postgresql_url(value: str, name: str) -> None:
    _require_nonblank(value, name)
    parsed_url = urlparse(value)
    if parsed_url.scheme not in {"postgresql", "postgres"} or not parsed_url.netloc:
        msg = f"{name} must be a PostgreSQL connection URL"
        raise SettingsError(msg)


__all__ = [
    "ApiSettings",
    "ApplicationSettings",
    "AuthProvider",
    "AuthSettings",
    "DatabaseSettings",
    "GeminiSettings",
    "LogLevel",
    "LoggingSettings",
    "LoreForgeSettings",
    "ObservabilitySettings",
    "OpenRouterSettings",
    "ProviderSelection",
    "ProviderSettings",
    "RuntimeEnvironment",
    "SettingsError",
    "StorageProvider",
    "StorageSettings",
    "load_settings",
]
