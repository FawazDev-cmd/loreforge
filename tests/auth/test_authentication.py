from uuid import UUID

import pytest

from loreforge.auth import (
    ApiKeyAuthenticator,
    Authenticator,
    AuthRepositoryError,
    InMemoryApiKeyRepository,
    InMemoryUserRepository,
    UserIdentity,
    UserRepository,
    hash_api_key,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000111")


def test_api_key_authenticator_returns_principal_for_valid_key() -> None:
    user = UserIdentity(user_id=USER_ID, display_name="Owner")
    repository = InMemoryApiKeyRepository(((hash_api_key("secret-key"), user),))
    authenticator = ApiKeyAuthenticator(repository)

    principal = authenticator.authenticate("secret-key")

    assert isinstance(authenticator, Authenticator)
    assert principal is not None
    assert principal.user == user


def test_api_key_authenticator_rejects_missing_or_invalid_key_safely() -> None:
    user = UserIdentity(user_id=USER_ID)
    repository = InMemoryApiKeyRepository(((hash_api_key("secret-key"), user),))
    authenticator = ApiKeyAuthenticator(repository)

    assert authenticator.authenticate(" ") is None
    assert authenticator.authenticate("wrong-key") is None


def test_in_memory_user_repository_crud_and_protocol() -> None:
    repository = InMemoryUserRepository()
    user = UserIdentity(user_id=USER_ID)

    repository.add(user)

    assert isinstance(repository, UserRepository)
    assert repository.get(USER_ID) == user
    assert repository.list() == (user,)
    with pytest.raises(AuthRepositoryError, match="user_id"):
        repository.add(user)


def test_user_identity_validation() -> None:
    with pytest.raises(ValueError, match="display_name"):
        UserIdentity(user_id=USER_ID, display_name=" ")
