"""Provider-independent authentication services."""

from hashlib import sha256
from typing import Protocol, runtime_checkable

from loreforge.auth.models import AuthenticatedPrincipal
from loreforge.auth.repository import ApiKeyRepository


@runtime_checkable
class Authenticator(Protocol):
    """Authenticate opaque credentials into a LoreForge principal."""

    def authenticate(self, credential: str) -> AuthenticatedPrincipal | None:
        """Return a principal for valid credentials."""
        ...


class DisabledAuthenticator:
    """Authenticator used when authentication is disabled."""

    def authenticate(self, credential: str) -> AuthenticatedPrincipal | None:
        return None


class ApiKeyAuthenticator:
    """Authenticate development API keys without storing plaintext secrets."""

    def __init__(self, repository: ApiKeyRepository) -> None:
        self._repository = repository

    def authenticate(self, credential: str) -> AuthenticatedPrincipal | None:
        if not credential.strip():
            return None
        user = self._repository.resolve(hash_api_key(credential))
        if user is None:
            return None
        return AuthenticatedPrincipal(user=user)


def hash_api_key(api_key: str) -> str:
    """Return the stable SHA-256 hash used for API-key lookup."""
    return sha256(api_key.encode("utf-8")).hexdigest()
