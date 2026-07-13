from uuid import UUID

from fastapi.testclient import TestClient

from loreforge.documents.upload import MAX_UPLOAD_SIZE_BYTES, PDF_MEDIA_TYPE
from loreforge.main import app

client = TestClient(app)


def test_upload_valid_pdf_returns_accepted_metadata() -> None:
    content = b"%PDF-1.7\ncontent"
    response = client.post(
        "/documents/upload",
        files={"file": ("../../reports/handbook.pdf", content, PDF_MEDIA_TYPE)},
    )

    assert response.status_code == 201
    body = response.json()
    assert UUID(body["document_id"])
    assert body["filename"] == "handbook.pdf"
    assert body["media_type"] == PDF_MEDIA_TYPE
    assert body["size_bytes"] == len(content)
    assert body["status"] == "accepted"


def test_upload_missing_file_returns_422() -> None:
    response = client.post("/documents/upload")

    assert response.status_code == 422


def test_upload_wrong_extension_returns_415() -> None:
    response = client.post(
        "/documents/upload",
        files={"file": ("handbook.txt", b"%PDF-1.7\ncontent", PDF_MEDIA_TYPE)},
    )

    assert response.status_code == 415


def test_upload_wrong_media_type_returns_415() -> None:
    response = client.post(
        "/documents/upload",
        files={"file": ("handbook.pdf", b"%PDF-1.7\ncontent", "text/plain")},
    )

    assert response.status_code == 415


def test_upload_empty_file_returns_400() -> None:
    response = client.post(
        "/documents/upload",
        files={"file": ("handbook.pdf", b"", PDF_MEDIA_TYPE)},
    )

    assert response.status_code == 400


def test_upload_invalid_signature_returns_415() -> None:
    response = client.post(
        "/documents/upload",
        files={"file": ("handbook.pdf", b"not a pdf", PDF_MEDIA_TYPE)},
    )

    assert response.status_code == 415


def test_upload_oversized_file_returns_413() -> None:
    content = b"%PDF-" + b"x" * (MAX_UPLOAD_SIZE_BYTES + 1 - len(b"%PDF-"))
    response = client.post(
        "/documents/upload",
        files={"file": ("handbook.pdf", content, PDF_MEDIA_TYPE)},
    )

    assert response.status_code == 413


def test_health_endpoint_continues_to_work() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "loreforge"}
