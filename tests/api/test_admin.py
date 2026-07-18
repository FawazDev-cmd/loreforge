from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from loreforge.api import admin
from loreforge.catalog import (
    CatalogService,
    CatalogServiceError,
    InMemoryCatalogRepository,
)
from loreforge.documents.upload import UnsupportedDocumentError
from loreforge.indexing import (
    DocumentAlreadyIndexedError,
    DocumentIndexingExecutionError,
    IndexedDocumentResult,
)
from loreforge.main import app

DOC1 = UUID("00000000-0000-0000-0000-000000000001")
DOC2 = UUID("00000000-0000-0000-0000-000000000002")
MISSING = UUID("00000000-0000-0000-0000-000000000099")
UPLOADED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeIndexingService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, object]] = []

    def index_pdf(
        self,
        *,
        document_id: UUID,
        filename: str | None,
        media_type: str | None,
        content: bytes,
    ) -> IndexedDocumentResult:
        self.calls.append(
            {
                "document_id": document_id,
                "filename": filename,
                "media_type": media_type,
                "content": content,
            }
        )
        if self.error is not None:
            raise self.error
        return IndexedDocumentResult(
            document_id=document_id,
            chunk_count=2,
            semantic_indexed_count=2,
            lexical_indexed_count=2,
        )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    service = CatalogService(InMemoryCatalogRepository())
    app.dependency_overrides[admin.get_catalog_service] = lambda: service
    monkeypatch.setattr(admin, "_new_document_id", lambda: DOC1)
    monkeypatch.setattr(admin, "_utc_now", lambda: UPLOADED_AT)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_health_endpoint_still_works(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "loreforge"}


def test_create_document(client: TestClient) -> None:
    response = client.post("/admin/documents", json=_create_payload())

    assert response.status_code == 201
    assert response.json() == {
        "document_id": str(DOC1),
        "filename": "policy.pdf",
        "uploaded_at": "2026-01-01T00:00:00Z",
        "page_count": 4,
        "chunk_count": 0,
        "status": "UPLOADED",
    }


def test_list_documents(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    ids = iter((DOC1, DOC2))
    monkeypatch.setattr(admin, "_new_document_id", lambda: next(ids))
    client.post("/admin/documents", json=_create_payload(filename="policy.pdf"))
    client.post("/admin/documents", json=_create_payload(filename="handbook.pdf"))

    response = client.get("/admin/documents")

    assert response.status_code == 200
    assert [item["document_id"] for item in response.json()["documents"]] == [
        str(DOC1),
        str(DOC2),
    ]


def test_get_document(client: TestClient) -> None:
    client.post("/admin/documents", json=_create_payload())

    response = client.get(f"/admin/documents/{DOC1}")

    assert response.status_code == 200
    assert response.json()["document_id"] == str(DOC1)
    assert response.json()["filename"] == "policy.pdf"


def test_get_missing_document_returns_404(client: TestClient) -> None:
    response = client.get(f"/admin/documents/{MISSING}")

    assert response.status_code == 404
    assert response.json() == {"detail": "document not found"}


def test_lifecycle_transitions(client: TestClient) -> None:
    client.post("/admin/documents", json=_create_payload())

    ingesting = client.post(f"/admin/documents/{DOC1}/ingesting")
    ready = client.post(
        f"/admin/documents/{DOC1}/ready",
        json={"page_count": 6, "chunk_count": 9},
    )
    deleted = client.post(f"/admin/documents/{DOC1}/deleted")

    assert ingesting.status_code == 200
    assert ingesting.json()["status"] == "INGESTING"
    assert ready.status_code == 200
    assert ready.json()["status"] == "READY"
    assert ready.json()["page_count"] == 6
    assert ready.json()["chunk_count"] == 9
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "DELETED"


def test_failed_and_deleted_document_state(client: TestClient) -> None:
    client.post("/admin/documents", json=_create_payload())

    failed = client.post(f"/admin/documents/{DOC1}/failed")
    deleted = client.post(f"/admin/documents/{DOC1}/deleted")

    assert failed.status_code == 200
    assert failed.json()["status"] == "FAILED"
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "DELETED"


def test_invalid_lifecycle_transition_returns_409(client: TestClient) -> None:
    client.post("/admin/documents", json=_create_payload())

    response = client.post(
        f"/admin/documents/{DOC1}/ready",
        json={"page_count": 1, "chunk_count": 1},
    )

    assert response.status_code == 409
    assert "transition" in response.json()["detail"]


def test_missing_document_transition_returns_404(client: TestClient) -> None:
    response = client.post(f"/admin/documents/{MISSING}/ingesting")

    assert response.status_code == 404
    assert response.json() == {"detail": "document not found"}


def test_invalid_uuid_returns_422(client: TestClient) -> None:
    response = client.get("/admin/documents/not-a-uuid")

    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"filename": " ", "page_count": 1, "chunk_count": 0},
        {"filename": "policy.pdf", "page_count": -1, "chunk_count": 0},
        {"filename": "policy.pdf", "page_count": 1, "chunk_count": -1},
    ],
)
def test_create_validation_failures_return_422(
    client: TestClient,
    payload: dict[str, object],
) -> None:
    response = client.post("/admin/documents", json=payload)

    assert response.status_code == 422


def test_ready_validation_failure_returns_422(client: TestClient) -> None:
    client.post("/admin/documents", json=_create_payload())
    client.post(f"/admin/documents/{DOC1}/ingesting")

    response = client.post(
        f"/admin/documents/{DOC1}/ready",
        json={"page_count": 1, "chunk_count": -1},
    )

    assert response.status_code == 422


def test_response_schema(client: TestClient) -> None:
    response = client.post("/admin/documents", json=_create_payload())

    assert set(response.json()) == {
        "document_id",
        "filename",
        "uploaded_at",
        "page_count",
        "chunk_count",
        "status",
    }
    assert set(client.get("/admin/documents").json()) == {"documents"}


def test_deterministic_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _create_document_with_fresh_client(monkeypatch)
    second = _create_document_with_fresh_client(monkeypatch)

    assert first == second


def _create_document_with_fresh_client(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    service = CatalogService(InMemoryCatalogRepository())
    app.dependency_overrides[admin.get_catalog_service] = lambda: service
    monkeypatch.setattr(admin, "_new_document_id", lambda: DOC1)
    monkeypatch.setattr(admin, "_utc_now", lambda: UPLOADED_AT)
    try:
        with TestClient(app) as isolated_client:
            response = isolated_client.post("/admin/documents", json=_create_payload())
            assert response.status_code == 201
            return response.json()
    finally:
        app.dependency_overrides.clear()


def _create_payload(
    *,
    filename: str = "policy.pdf",
    page_count: int = 4,
    chunk_count: int = 2,
) -> dict[str, object]:
    return {
        "filename": filename,
        "page_count": page_count,
        "chunk_count": chunk_count,
    }


def test_index_document_success_delegates_to_app_state_service(
    client: TestClient,
) -> None:
    service = FakeIndexingService()
    app.dependency_overrides[admin.get_document_indexing_service] = lambda: service

    response = client.post(
        f"/admin/documents/{DOC1}/index",
        files={"file": ("policy.pdf", b"%PDF- fake", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "document_id": str(DOC1),
        "chunk_count": 2,
        "semantic_indexed_count": 2,
        "lexical_indexed_count": 2,
    }
    assert service.calls == [
        {
            "document_id": DOC1,
            "filename": "policy.pdf",
            "media_type": "application/pdf",
            "content": b"%PDF- fake",
        }
    ]


def test_index_document_unknown_document_returns_404(client: TestClient) -> None:
    service = FakeIndexingService(CatalogServiceError("document_id does not exist"))
    app.dependency_overrides[admin.get_document_indexing_service] = lambda: service

    response = client.post(
        f"/admin/documents/{MISSING}/index",
        files={"file": ("policy.pdf", b"%PDF- fake", "application/pdf")},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "document not found"}


def test_index_document_already_ready_returns_409(client: TestClient) -> None:
    service = FakeIndexingService(DocumentAlreadyIndexedError("raw duplicate detail"))
    app.dependency_overrides[admin.get_document_indexing_service] = lambda: service

    response = client.post(
        f"/admin/documents/{DOC1}/index",
        files={"file": ("policy.pdf", b"%PDF- fake", "application/pdf")},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "document is already indexed"}


def test_index_document_invalid_lifecycle_returns_409(client: TestClient) -> None:
    service = FakeIndexingService(CatalogServiceError("cannot transition secret"))
    app.dependency_overrides[admin.get_document_indexing_service] = lambda: service

    response = client.post(
        f"/admin/documents/{DOC1}/index",
        files={"file": ("policy.pdf", b"%PDF- fake", "application/pdf")},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "document lifecycle does not allow indexing"}


def test_index_document_invalid_upload_returns_422(client: TestClient) -> None:
    service = FakeIndexingService(UnsupportedDocumentError("raw upload detail"))
    app.dependency_overrides[admin.get_document_indexing_service] = lambda: service

    response = client.post(
        f"/admin/documents/{DOC1}/index",
        files={"file": ("policy.txt", b"not pdf", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid PDF upload"}


def test_index_document_runtime_failure_returns_safe_503(client: TestClient) -> None:
    service = FakeIndexingService(DocumentIndexingExecutionError("raw model detail"))
    app.dependency_overrides[admin.get_document_indexing_service] = lambda: service

    response = client.post(
        f"/admin/documents/{DOC1}/index",
        files={"file": ("policy.pdf", b"%PDF- fake", "application/pdf")},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "document indexing is temporarily unavailable"}
    assert "raw model detail" not in response.text


def test_index_document_missing_file_returns_422(client: TestClient) -> None:
    response = client.post(f"/admin/documents/{DOC1}/index")

    assert response.status_code == 422
