"""Framework-independent authentication boundary."""

from loreforge.auth.models import (
    AuthenticatedPrincipal,
    DocumentOwnership,
    UserIdentity,
)
from loreforge.auth.repository import (
    ApiKeyRepository,
    AuthRepositoryError,
    InMemoryApiKeyRepository,
    InMemoryUserRepository,
    UserRepository,
)
from loreforge.auth.service import (
    ApiKeyAuthenticator,
    Authenticator,
    DisabledAuthenticator,
    hash_api_key,
)

__all__ = [
    "ApiKeyAuthenticator",
    "ApiKeyRepository",
    "AuthRepositoryError",
    "AuthenticatedPrincipal",
    "Authenticator",
    "DisabledAuthenticator",
    "DocumentOwnership",
    "InMemoryApiKeyRepository",
    "InMemoryUserRepository",
    "UserIdentity",
    "UserRepository",
    "hash_api_key",
]
