from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from loreforge.application import create_application_container
from loreforge.database import DatabaseRuntime
from loreforge.main import create_app


def test_readiness_requires_started_application_lifespan() -> None:
    client = TestClient(create_app())

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "service": "loreforge"}


def test_readiness_returns_ready_after_startup() -> None:
    application = create_app()

    with TestClient(application) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "loreforge"}


def test_readiness_checks_configured_database() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    runtime = DatabaseRuntime(
        engine=engine,
        session_factory=sessionmaker(bind=engine, expire_on_commit=False),
    )
    container = replace(create_application_container(), database=runtime)
    application = create_app(container_factory=lambda: container)

    try:
        with TestClient(application) as client:
            response = client.get("/ready")
    finally:
        engine.dispose()

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "loreforge"}


def test_readiness_failure_uses_safe_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    runtime = DatabaseRuntime(
        engine=engine,
        session_factory=sessionmaker(bind=engine, expire_on_commit=False),
    )
    container = replace(create_application_container(), database=runtime)
    application = create_app(container_factory=lambda: container)

    def raise_health_error(self: DatabaseRuntime) -> None:
        raise RuntimeError("raw database secret")

    monkeypatch.setattr(DatabaseRuntime, "check_health", raise_health_error)
    try:
        with TestClient(application) as client:
            response = client.get("/ready")
    finally:
        engine.dispose()

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "service": "loreforge"}
    assert "raw database secret" not in response.text


def test_startup_and_shutdown_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    application = create_app()

    with caplog.at_level("INFO", logger="loreforge.main"):
        with TestClient(application):
            pass

    assert "starting LoreForge application" in caplog.messages
    assert "LoreForge application startup complete" in caplog.messages
    assert "shutting down LoreForge application" in caplog.messages
    assert "LoreForge application shutdown complete" in caplog.messages
