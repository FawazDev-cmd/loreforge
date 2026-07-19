from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from loreforge.api import admin
from loreforge.main import create_app
from loreforge.settings import load_settings

DOC1 = UUID("00000000-0000-0000-0000-000000000001")
USER1 = UUID("00000000-0000-0000-0000-000000000111")
USER2 = UUID("00000000-0000-0000-0000-000000000222")
UPLOADED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    settings = load_settings(
        {
            "LOREFORGE_AUTH_PROVIDER": "api_key",
            "LOREFORGE_AUTH_API_KEYS": (
                f"{USER1}:owner-one-key:Owner One,{USER2}:owner-two-key:Owner Two"
            ),
        }
    )
    application = create_app(settings=settings)
    monkeypatch.setattr(admin, "_new_document_id", lambda: DOC1)
    monkeypatch.setattr(admin, "_utc_now", lambda: UPLOADED_AT)
    with TestClient(application) as test_client:
        yield test_client


def test_missing_and_invalid_credentials_return_401(client: TestClient) -> None:
    missing = client.get("/admin/documents")
    invalid = client.get(
        "/admin/documents",
        headers={"Authorization": "Bearer wrong-key"},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert "wrong-key" not in invalid.text


def test_valid_authentication_allows_owner_to_manage_document(
    client: TestClient,
) -> None:
    created = client.post(
        "/admin/documents",
        json={"filename": "policy.pdf", "page_count": 1, "chunk_count": 0},
        headers=_auth("owner-one-key"),
    )
    listed = client.get("/admin/documents", headers=_auth("owner-one-key"))
    fetched = client.get(f"/admin/documents/{DOC1}", headers=_auth("owner-one-key"))
    failed = client.post(
        f"/admin/documents/{DOC1}/failed", headers=_auth("owner-one-key")
    )
    deleted = client.post(
        f"/admin/documents/{DOC1}/deleted",
        headers=_auth("owner-one-key"),
    )

    assert created.status_code == 201
    assert listed.status_code == 200
    assert [item["document_id"] for item in listed.json()["documents"]] == [str(DOC1)]
    assert fetched.status_code == 200
    assert failed.status_code == 200
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "DELETED"


def test_cross_owner_document_access_is_not_found(client: TestClient) -> None:
    response = client.post(
        "/admin/documents",
        json={"filename": "policy.pdf", "page_count": 1, "chunk_count": 0},
        headers=_auth("owner-one-key"),
    )
    assert response.status_code == 201

    listed = client.get("/admin/documents", headers=_auth("owner-two-key"))
    fetched = client.get(f"/admin/documents/{DOC1}", headers=_auth("owner-two-key"))
    deleted = client.post(
        f"/admin/documents/{DOC1}/deleted",
        headers=_auth("owner-two-key"),
    )

    assert listed.json() == {"documents": []}
    assert fetched.status_code == 404
    assert fetched.json() == {"detail": "document not found"}
    assert deleted.status_code == 404


def test_upload_and_ask_routes_require_auth_when_enabled(client: TestClient) -> None:
    upload = client.post(
        "/documents/upload",
        files={"file": ("policy.pdf", b"%PDF- fake", "application/pdf")},
    )
    ask = client.post("/ask", json={"question": "What changed?"})

    assert upload.status_code == 401
    assert ask.status_code == 401


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}
