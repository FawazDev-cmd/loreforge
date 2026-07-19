"""FastAPI application entrypoint."""

from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from loreforge.api.admin import router as admin_router
from loreforge.api.askme import router as askme_router
from loreforge.api.documents import router as documents_router
from loreforge.application import ApplicationContainer, create_application_container
from loreforge.settings import LoreForgeSettings, load_settings


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
        container = resolved_container_factory()
        application.state.container = container
        try:
            yield
        finally:
            container.close()

    application = FastAPI(
        title=runtime_settings.application.api_title,
        version=runtime_settings.application.api_version,
        lifespan=lifespan,
    )
    application.include_router(admin_router)
    application.include_router(askme_router)
    application.include_router(documents_router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "healthy",
            "service": runtime_settings.application.service_name,
        }

    return application


app = create_app()
