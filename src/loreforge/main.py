"""FastAPI application entrypoint."""

from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from loreforge.api.admin import router as admin_router
from loreforge.api.askme import router as askme_router
from loreforge.api.documents import router as documents_router
from loreforge.application import ApplicationContainer, create_application_container


def create_app(
    *,
    container_factory: Callable[
        [], ApplicationContainer
    ] = create_application_container,
) -> FastAPI:
    """Create the LoreForge FastAPI application."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.container = container_factory()
        yield

    application = FastAPI(title="LoreForge", version="0.1.0", lifespan=lifespan)
    application.include_router(admin_router)
    application.include_router(askme_router)
    application.include_router(documents_router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy", "service": "loreforge"}

    return application


app = create_app()
