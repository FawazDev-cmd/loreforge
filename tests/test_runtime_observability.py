import logging
from dataclasses import replace
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from loreforge.application import create_application_container
from loreforge.database import DatabaseRuntime
from loreforge.main import create_app
from loreforge.observability import current_request_id, current_user_id
from loreforge.settings import load_settings

REQUEST_ID = UUID("00000000-0000-0000-0000-00000000a001")
USER_ID = UUID("00000000-0000-0000-0000-00000000b001")


def test_request_id_header_is_preserved_and_context_is_reset() -> None:
    application = create_app()

    with TestClient(application) as client:
        response = client.get("/health", headers={"X-Request-ID": str(REQUEST_ID)})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == str(REQUEST_ID)
    assert current_request_id() is None
    assert current_user_id() is None


def test_invalid_request_id_header_is_replaced() -> None:
    application = create_app()

    with TestClient(application) as client:
        response = client.get("/health", headers={"X-Request-ID": "not-a-uuid"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "not-a-uuid"
    assert UUID(response.headers["X-Request-ID"])


def test_http_request_metrics_use_normalized_low_cardinality_labels() -> None:
    container = create_application_container()
    application = create_app(container_factory=lambda: container)

    with TestClient(application) as client:
        client.get("/health")
        client.get("/admin/documents/00000000-0000-0000-0000-000000000001")

    snapshot = container.operational_metrics.snapshot().as_dict()
    counters = {
        (item["name"], tuple(sorted(item["labels"].items()))): item["value"]
        for item in snapshot["counters"]
        if item["name"] == "http_request_total"
    }
    assert (
        counters[
            (
                "http_request_total",
                (
                    ("method", "GET"),
                    ("route", "/health"),
                    ("status_category", "2xx"),
                ),
            )
        ]
        == 1
    )
    assert (
        counters[
            (
                "http_request_total",
                (
                    ("method", "GET"),
                    ("route", "/admin/documents/{document_id}"),
                    ("status_category", "4xx"),
                ),
            )
        ]
        == 1
    )


def test_metrics_endpoint_returns_snapshot_without_request_or_user_labels() -> None:
    application = create_app()

    with TestClient(application) as client:
        client.get("/health")
        response = client.get("/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "metrics" in payload
    labels = [
        label
        for section in ("counters", "durations")
        for metric in payload["metrics"][section]
        for label in metric["labels"]
    ]
    assert "request_id" not in labels
    assert "user_id" not in labels
    assert "document_id" not in labels
    assert "filename" not in labels
    assert "question" not in labels


def test_metrics_endpoint_requires_auth_when_auth_is_enabled() -> None:
    settings = load_settings(
        {
            "LOREFORGE_AUTH_PROVIDER": "api_key",
            "LOREFORGE_AUTH_API_KEYS": f"{USER_ID}:safe-test-key:Owner",
        }
    )
    application = create_app(settings=settings)

    with TestClient(application) as client:
        missing = client.get("/metrics")
        allowed = client.get(
            "/metrics",
            headers={"Authorization": "Bearer safe-test-key"},
        )

    assert missing.status_code == 401
    assert allowed.status_code == 200


def test_request_logging_omits_credentials_and_content(
    caplog,
) -> None:
    settings = load_settings(
        {
            "LOREFORGE_AUTH_PROVIDER": "api_key",
            "LOREFORGE_AUTH_API_KEYS": f"{USER_ID}:super-secret-key:Owner",
        }
    )
    application = create_app(settings=settings)

    with caplog.at_level(logging.INFO, logger="loreforge.main"):
        with TestClient(application) as client:
            response = client.get(
                "/admin/documents",
                headers={
                    "Authorization": "Bearer super-secret-key",
                    "X-Request-ID": str(REQUEST_ID),
                },
            )

    assert response.status_code == 200
    combined = "\n".join(caplog.messages)
    assert "super-secret-key" not in combined
    records = [
        record
        for record in caplog.records
        if record.message == "http request completed"
    ]
    assert records
    assert records[-1].request_id == str(REQUEST_ID)
    assert records[-1].method == "GET"
    assert records[-1].route == "/admin/documents"
    assert records[-1].status_code == 200
    assert records[-1].authenticated is True
    assert records[-1].error_category is None


def test_readiness_records_database_health_metrics() -> None:
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
    snapshot = container.operational_metrics.snapshot().as_dict()
    counters = {
        (item["name"], tuple(sorted(item["labels"].items()))): item["value"]
        for item in snapshot["counters"]
    }
    assert (
        counters[
            (
                "database_readiness_check_total",
                (("success", "True"),),
            )
        ]
        == 1
    )
