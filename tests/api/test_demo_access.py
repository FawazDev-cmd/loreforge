from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from loreforge.api import askme
from loreforge.askme import AskMeCitation, AskMeRequest, AskMeResult
from loreforge.main import create_app
from loreforge.settings import load_settings

USER_A = UUID("00000000-0000-0000-0000-000000000a01")
USER_B = UUID("00000000-0000-0000-0000-000000000a02")
DEMO_USER = UUID("00000000-0000-0000-0000-000000000d01")
REQUEST_ID = UUID("00000000-0000-0000-0000-000000000001")
DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000201")
CHUNK_ID = UUID("00000000-0000-0000-0000-000000000101")
QUESTION = "What is the password policy?"


class SuccessfulService:
    def __init__(self) -> None:
        self.requests: list[AskMeRequest] = []

    def ask(self, request: AskMeRequest) -> AskMeResult:
        self.requests.append(request)
        return AskMeResult(
            request_id=REQUEST_ID,
            question=request.question,
            answer="Passwords must meet the documented policy [S1].",
            citations=(
                AskMeCitation(
                    citation_id="S1",
                    document_id=DOCUMENT_ID,
                    filename="security-policy.pdf",
                    page_number=2,
                    chunk_id=CHUNK_ID,
                ),
            ),
        )


@pytest.fixture()
def client() -> Iterator[TestClient]:
    settings = load_settings(
        {
            "LOREFORGE_ENVIRONMENT": "testing",
            "LOREFORGE_AUTH_PROVIDER": "api_key",
            "LOREFORGE_AUTH_API_KEYS": (
                f"{USER_A}:owner-a-key:Owner A,"
                f"{USER_B}:owner-b-key:Owner B,"
                f"{DEMO_USER}:demo-key:Recruiter Demo"
            ),
            "LOREFORGE_AUTH_DEMO_USER_IDS": str(DEMO_USER),
            "LOREFORGE_DEMO_ASK_RATE_LIMIT_REQUESTS": "1",
            "LOREFORGE_DEMO_ASK_RATE_LIMIT_WINDOW_SECONDS": "60",
            "LOREFORGE_DOCUMENT_EMBEDDINGS_PROVIDER": "disabled",
            "LOREFORGE_QUERY_EMBEDDINGS_PROVIDER": "disabled",
            "LOREFORGE_RERANKER_PROVIDER": "disabled",
            "LOREFORGE_LLM_PROVIDER": "disabled",
            "LOREFORGE_DATABASE_URL": "",
            "LOREFORGE_DATABASE_MIGRATIONS_ENABLED": "false",
        }
    )
    application = create_app(settings=settings)
    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()


def test_askme_receives_authenticated_owner_identity(client: TestClient) -> None:
    service = SuccessfulService()
    client.app.dependency_overrides[askme.get_askme_service] = lambda: service

    owner_a = client.post(
        "/ask", json={"question": QUESTION}, headers=_auth("owner-a-key")
    )
    owner_b = client.post(
        "/ask", json={"question": QUESTION}, headers=_auth("owner-b-key")
    )

    assert owner_a.status_code == 200
    assert owner_b.status_code == 200
    assert [request.owner_user_id for request in service.requests] == [USER_A, USER_B]


def test_demo_identity_can_read_documents_and_ask_once(client: TestClient) -> None:
    service = SuccessfulService()
    client.app.dependency_overrides[askme.get_askme_service] = lambda: service

    documents = client.get("/admin/documents", headers=_auth("demo-key"))
    ask_response = client.post(
        "/ask",
        json={"question": QUESTION},
        headers=_auth("demo-key"),
    )

    assert documents.status_code == 200
    assert documents.json() == {"documents": []}
    assert ask_response.status_code == 200
    assert service.requests[0].owner_user_id == DEMO_USER


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        (
            "post",
            "/admin/documents",
            {"json": {"filename": "policy.pdf", "page_count": 1, "chunk_count": 0}},
        ),
        (
            "post",
            f"/admin/documents/{DOCUMENT_ID}/index",
            {"files": {"file": ("policy.pdf", b"%PDF- fake", "application/pdf")}},
        ),
        ("post", f"/admin/documents/{DOCUMENT_ID}/ingesting", {}),
        (
            "post",
            f"/admin/documents/{DOCUMENT_ID}/ready",
            {"json": {"page_count": 1, "chunk_count": 1}},
        ),
        ("post", f"/admin/documents/{DOCUMENT_ID}/failed", {}),
        ("post", f"/admin/documents/{DOCUMENT_ID}/deleted", {}),
        ("delete", f"/admin/documents/{DOCUMENT_ID}", {}),
        (
            "post",
            "/documents/upload",
            {"files": {"file": ("policy.pdf", b"%PDF- fake", "application/pdf")}},
        ),
    ],
)
def test_demo_identity_cannot_perform_workspace_mutations(
    client: TestClient,
    method: str,
    path: str,
    kwargs: dict[str, object],
) -> None:
    response = getattr(client, method)(path, headers=_auth("demo-key"), **kwargs)

    assert response.status_code == 403
    assert response.json() == {"detail": "demo access is read-only"}


def test_demo_identity_cannot_access_metrics(client: TestClient) -> None:
    response = client.get("/metrics", headers=_auth("demo-key"))

    assert response.status_code == 403
    assert response.json() == {"detail": "demo access is read-only"}


def test_demo_ask_rate_limit_returns_429(client: TestClient) -> None:
    service = SuccessfulService()
    client.app.dependency_overrides[askme.get_askme_service] = lambda: service

    first = client.post("/ask", json={"question": QUESTION}, headers=_auth("demo-key"))
    second = client.post("/ask", json={"question": QUESTION}, headers=_auth("demo-key"))

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json() == {"detail": "demo ask rate limit exceeded"}
    assert len(service.requests) == 1


def test_demo_rate_limit_does_not_apply_to_normal_users(client: TestClient) -> None:
    service = SuccessfulService()
    client.app.dependency_overrides[askme.get_askme_service] = lambda: service

    first = client.post(
        "/ask", json={"question": QUESTION}, headers=_auth("owner-a-key")
    )
    second = client.post(
        "/ask", json={"question": QUESTION}, headers=_auth("owner-a-key")
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(service.requests) == 2


def test_normal_identity_keeps_existing_mutation_behavior(client: TestClient) -> None:
    create_response = client.post(
        "/admin/documents",
        json={"filename": "policy.pdf", "page_count": 1, "chunk_count": 0},
        headers=_auth("owner-a-key"),
    )

    assert create_response.status_code == 201


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}
