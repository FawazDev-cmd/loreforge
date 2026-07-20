"""FastAPI application entrypoint."""

import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated, AsyncIterator
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

from loreforge.api.admin import router as admin_router
from loreforge.api.askme import router as askme_router
from loreforge.api.auth import get_current_principal
from loreforge.api.documents import router as documents_router
from loreforge.application import ApplicationContainer, create_application_container
from loreforge.auth import AuthenticatedPrincipal
from loreforge.observability import (
    current_user_id,
    reset_request_id,
    reset_user_id,
    set_request_id,
    set_user_id,
)
from loreforge.settings import LoreForgeSettings, load_settings

_logger = logging.getLogger(__name__)
_REQUEST_ID_HEADER = "X-Request-ID"


def create_app(
    *,
    container_factory: Callable[[], ApplicationContainer] | None = None,
    settings: LoreForgeSettings | None = None,
) -> FastAPI:
    """Create the LoreForge FastAPI application."""
    runtime_settings = load_settings() if settings is None else settings
    resolved_container_factory = container_factory or (
        lambda: create_application_container(settings=runtime_settings)
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        _logger.info("starting LoreForge application")
        container = resolved_container_factory()
        application.state.container = container
        _logger.info("LoreForge application startup complete")
        try:
            yield
        finally:
            _logger.info("shutting down LoreForge application")
            container.close()
            _logger.info("LoreForge application shutdown complete")

    application = FastAPI(
        title=runtime_settings.application.api_title,
        version=runtime_settings.application.api_version,
        lifespan=lifespan,
    )
    application.include_router(admin_router)
    application.include_router(askme_router)
    application.include_router(documents_router)

    @application.middleware("http")
    async def request_observability(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = _request_id_from_header(request.headers.get(_REQUEST_ID_HEADER))
        request_token = set_request_id(request_id)
        user_token = set_user_id(None)
        start = perf_counter()
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_category: str | None = None
        response: Response | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            error_category = type(exc).__name__
            _logger.exception(
                "http request failed",
                extra=_request_log_extra(
                    request=request,
                    request_id=request_id,
                    status_code=status_code,
                    duration_ms=float((perf_counter() - start) * 1000.0),
                    error_category=error_category,
                ),
            )
            raise
        finally:
            duration_ms = float((perf_counter() - start) * 1000.0)
            if response is not None:
                response.headers[_REQUEST_ID_HEADER] = str(request_id)
            _record_http_metrics(
                application,
                method=request.method,
                route=_normalized_route(request),
                status_code=status_code,
                duration_ms=duration_ms,
            )
            if runtime_settings.logging.request_logging_enabled:
                _logger.info(
                    "http request completed",
                    extra=_request_log_extra(
                        request=request,
                        request_id=request_id,
                        status_code=status_code,
                        duration_ms=duration_ms,
                        error_category=error_category,
                    ),
                )
            reset_user_id(user_token)
            reset_request_id(request_token)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "healthy",
            "service": runtime_settings.application.service_name,
        }

    @application.get("/metrics")
    def metrics(
        _principal: Annotated[
            AuthenticatedPrincipal | None,
            Depends(get_current_principal),
        ],
    ) -> dict[str, object]:
        container = getattr(application.state, "container", None)
        if type(container) is not ApplicationContainer:
            return {"status": "unavailable", "metrics": {}}
        return {
            "status": "ok",
            "metrics": container.operational_metrics.snapshot().as_dict(),
            "query_trace_count": len(container.metrics_recorder.snapshot()),
        }

    @application.get("/ready", response_model=None)
    def ready() -> dict[str, str] | JSONResponse:
        container = getattr(application.state, "container", None)
        if type(container) is not ApplicationContainer:
            return _not_ready(runtime_settings.application.service_name)

        if container.database is not None:
            readiness_start = perf_counter()
            try:
                container.database.check_health()
            except Exception:
                _record_database_readiness(container, readiness_start, success=False)
                _logger.warning("readiness database health check failed")
                return _not_ready(runtime_settings.application.service_name)
            _record_database_readiness(container, readiness_start, success=True)

        return {
            "status": "ready",
            "service": runtime_settings.application.service_name,
        }

    return application


def _request_id_from_header(value: str | None) -> UUID:
    if value is None:
        return uuid4()
    try:
        return UUID(value)
    except ValueError:
        return uuid4()


def _normalized_route(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if type(route_path) is str and route_path:
        return route_path
    return request.url.path


def _request_log_extra(
    *,
    request: Request,
    request_id: UUID,
    status_code: int,
    duration_ms: float,
    error_category: str | None,
) -> dict[str, object]:
    return {
        "request_id": str(request_id),
        "method": request.method,
        "route": _normalized_route(request),
        "status_code": status_code,
        "duration_ms": duration_ms,
        "authenticated": bool(getattr(request.state, "authenticated", False))
        or current_user_id() is not None,
        "error_category": error_category,
    }


def _record_http_metrics(
    application: FastAPI,
    *,
    method: str,
    route: str,
    status_code: int,
    duration_ms: float,
) -> None:
    container = getattr(application.state, "container", None)
    if type(container) is not ApplicationContainer:
        return
    labels = {
        "method": method,
        "route": route,
        "status_category": f"{status_code // 100}xx",
    }
    container.operational_metrics.increment("http_request_total", labels=labels)
    container.operational_metrics.observe_duration(
        "http_request_duration_ms",
        duration_ms,
        labels=labels,
    )


def _record_database_readiness(
    container: ApplicationContainer,
    start: float,
    *,
    success: bool,
) -> None:
    labels = {"success": str(success)}
    duration_ms = float((perf_counter() - start) * 1000.0)
    container.operational_metrics.increment(
        "database_readiness_check_total",
        labels=labels,
    )
    container.operational_metrics.observe_duration(
        "database_readiness_duration_ms",
        duration_ms,
        labels=labels,
    )


def _not_ready(service_name: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "not_ready",
            "service": service_name,
        },
    )


app = create_app()
