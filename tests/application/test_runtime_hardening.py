from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from loreforge.application import ApplicationRuntimeState, create_application_container
from loreforge.database import DatabaseRuntime
from loreforge.main import create_app
from loreforge.settings import load_settings


def test_runtime_state_defaults_to_not_ready() -> None:
    state = ApplicationRuntimeState()

    assert state.ready is False


def test_readiness_requires_started_application_lifespan() -> None:
    application = create_app(settings=load_settings({}))
    client = TestClient(application)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"ready": False}


def test_successful_warm_up_marks_runtime_state_ready() -> None:
    container = replace(
        create_application_container(settings=load_settings({})),
        reranker=WarmableReranker(),
    )
    application = create_app(container_factory=lambda: container)
    state = application.state.runtime_state

    assert state.ready is False
    with TestClient(application):
        assert state.ready is True


def test_failed_warm_up_never_marks_runtime_state_ready() -> None:
    container = replace(
        create_application_container(settings=load_settings({})),
        reranker=FailingWarmableReranker(),
    )
    application = create_app(container_factory=lambda: container)
    state = application.state.runtime_state

    with pytest.raises(RuntimeError, match="warm-up failed"):
        with TestClient(application):
            pass

    assert state.ready is False


def test_ready_returns_200_after_successful_warm_up() -> None:
    application = create_app(settings=load_settings({}))

    with TestClient(application) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"ready": True}


def test_health_endpoint_remains_unchanged() -> None:
    application = create_app(settings=load_settings({}))
    client = TestClient(application)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "loreforge"}


def test_shutdown_marks_runtime_state_not_ready() -> None:
    application = create_app(settings=load_settings({}))
    state = application.state.runtime_state

    with TestClient(application):
        assert state.ready is True

    assert state.ready is False


def test_repeated_ready_reads_do_not_repeat_warm_up_or_external_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    runtime = DatabaseRuntime(
        engine=engine,
        session_factory=sessionmaker(bind=engine, expire_on_commit=False),
    )
    reranker = WarmableReranker()
    container = replace(
        create_application_container(settings=load_settings({})),
        database=runtime,
        reranker=reranker,
    )
    application = create_app(container_factory=lambda: container)
    state = application.state.runtime_state
    database_health_checks = 0

    def count_database_health_check(self: DatabaseRuntime) -> None:
        nonlocal database_health_checks
        database_health_checks += 1
        raise RuntimeError("raw database detail")

    monkeypatch.setattr(
        DatabaseRuntime,
        "check_health",
        count_database_health_check,
    )
    try:
        with TestClient(application) as client:
            assert application.state.runtime_state is state
            responses = [client.get("/ready") for _ in range(3)]
    finally:
        engine.dispose()

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert [response.json() for response in responses] == [
        {"ready": True},
        {"ready": True},
        {"ready": True},
    ]
    assert application.state.runtime_state is state
    assert reranker.warm_up_calls == 1
    assert database_health_checks == 0


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
