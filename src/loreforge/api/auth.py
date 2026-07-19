"""HTTP authentication dependencies for protected API routes."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from loreforge.application import ApplicationContainer
from loreforge.auth import AuthenticatedPrincipal
from loreforge.settings import AuthProvider

_APPLICATION_UNAVAILABLE_DETAIL = "Application services are unavailable."
_AUTHENTICATION_REQUIRED_DETAIL = "authentication required"

_bearer = HTTPBearer(auto_error=False)


def get_current_principal(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer),
    ] = None,
) -> AuthenticatedPrincipal | None:
    """Return the authenticated principal when auth is enabled."""
    container = getattr(request.app.state, "container", None)
    if type(container) is not ApplicationContainer:
        return None
    if container.settings.auth.provider is AuthProvider.DISABLED:
        return None

    if (
        container.settings.auth.provider is not AuthProvider.API_KEY
        or credentials is None
        or credentials.scheme.lower() != "bearer"
    ):
        raise _unauthorized()

    principal = container.authenticator.authenticate(credentials.credentials)
    if principal is None:
        raise _unauthorized()
    return principal


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_AUTHENTICATION_REQUIRED_DETAIL,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _application_container_from_request(request: Request) -> ApplicationContainer:
    container = getattr(request.app.state, "container", None)
    if type(container) is not ApplicationContainer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_APPLICATION_UNAVAILABLE_DETAIL,
        )
    return container
