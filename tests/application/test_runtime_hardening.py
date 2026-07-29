from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from loreforge.application import create_application_container
from loreforge.database import DatabaseRuntime
from loreforge.main import create_app
from loreforge.settings import load_settings


def test_readiness_requires_started_application_lifespan() -> None:
    client = TestClient(create_app(settings=load_settings({})))

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "service": "loreforge"}


def test_readiness_returns_ready_after_startup() -> None:
    application = create_app(settings=load_settings({}))

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
    container = replace(
        create_application_container(settings=load_settings({})), database=runtime
    )
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
    container = replace(
        create_application_container(settings=load_settings({})), database=runtime
    )
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
    application = create_app(settings=load_settings({}))

    with caplog.at_level("INFO", logger="loreforge.main"):
        with TestClient(application):
            pass

    assert "starting LoreForge application" in caplog.messages
    assert "LoreForge application startup complete" in caplog.messages
    assert "shutting down LoreForge application" in caplog.messages
    assert "LoreForge application shutdown complete" in caplog.messages


def test_startup_invokes_container_warm_up_once() -> None:
    container = replace(
        create_application_container(settings=load_settings({})),
        reranker=WarmableReranker(),
    )
    application = create_app(container_factory=lambda: container)

    with TestClient(application):
        pass

    assert container.reranker is not None
    assert container.reranker.warm_up_calls == 1


def test_startup_warm_up_failure_fails_application_startup() -> None:
    container = replace(
        create_application_container(settings=load_settings({})),
        reranker=FailingWarmableReranker(),
    )
    application = create_app(container_factory=lambda: container)

    with pytest.raises(RuntimeError, match="warm-up failed"):
        with TestClient(application):
            pass


class WarmableReranker:
    def __init__(self) -> None:
        self.warm_up_calls = 0

    def warm_up(self) -> None:
        self.warm_up_calls += 1

    def score(self, requests: tuple[object, ...]) -> tuple[object, ...]:
        return ()


class FailingWarmableReranker(WarmableReranker):
    def warm_up(self) -> None:
        raise RuntimeError("warm-up failed")
