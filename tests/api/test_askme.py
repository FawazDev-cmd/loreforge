from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from loreforge.api import askme
from loreforge.askme import (
    AskMeCitation,
    AskMeGroundingError,
    AskMeRequest,
    AskMeResult,
    AskMeUnavailableError,
)
from loreforge.main import app

REQUEST_ID = UUID("00000000-0000-0000-0000-000000000001")
DOCUMENT_ID_1 = UUID("00000000-0000-0000-0000-000000000201")
DOCUMENT_ID_2 = UUID("00000000-0000-0000-0000-000000000202")
CHUNK_ID_1 = UUID("00000000-0000-0000-0000-000000000101")
CHUNK_ID_2 = UUID("00000000-0000-0000-0000-000000000102")
QUESTION = "What is the refund policy?"
ANSWER = "Refund requests must be submitted within 14 days [S1]."


class SuccessfulService:
    def __init__(self, result: AskMeResult | None = None) -> None:
        self.result = result or _result()
        self.requests: list[AskMeRequest] = []

    def ask(self, request: AskMeRequest) -> AskMeResult:
        self.requests.append(request)
        return self.result


class RaisingService:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def ask(self, request: AskMeRequest) -> AskMeResult:
        raise self.error


@pytest.fixture
def client() -> Iterator[TestClient]:
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_health_endpoint_remains_available(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "loreforge"}


def test_admin_routes_remain_registered(client: TestClient) -> None:
    response = client.get("/admin/documents")

    assert response.status_code == 200
    assert "documents" in response.json()


def test_successful_ask_request(client: TestClient) -> None:
    service = SuccessfulService()
    app.dependency_overrides[askme.get_askme_service] = lambda: service

    response = client.post("/ask", json={"question": QUESTION})

    assert response.status_code == 200
    assert service.requests == [AskMeRequest(QUESTION)]


def test_response_schema(client: TestClient) -> None:
    app.dependency_overrides[askme.get_askme_service] = lambda: SuccessfulService()

    response = client.post("/ask", json={"question": QUESTION})

    assert set(response.json()) == {
        "request_id",
        "question",
        "answer",
        "citations",
    }
    assert set(response.json()["citations"][0]) == {
        "citation_id",
        "document_id",
        "filename",
        "page_number",
        "chunk_id",
    }


def test_question_and_answer_preserved(client: TestClient) -> None:
    app.dependency_overrides[askme.get_askme_service] = lambda: SuccessfulService()

    response = client.post("/ask", json={"question": QUESTION})

    body = response.json()
    assert body["question"] == QUESTION
    assert body["answer"] == ANSWER


def test_citation_ordering_preserved(client: TestClient) -> None:
    citations = (
        _citation("S2", DOCUMENT_ID_2, "shipping-policy.pdf", 5, CHUNK_ID_2),
        _citation("S1", DOCUMENT_ID_1, "refund-policy.pdf", 2, CHUNK_ID_1),
    )
    app.dependency_overrides[askme.get_askme_service] = lambda: SuccessfulService(
        _result(citations=citations)
    )

    response = client.post("/ask", json={"question": QUESTION})

    assert [item["citation_id"] for item in response.json()["citations"]] == [
        "S2",
        "S1",
    ]


def test_citation_uuid_serialization(client: TestClient) -> None:
    app.dependency_overrides[askme.get_askme_service] = lambda: SuccessfulService()

    response = client.post("/ask", json={"question": QUESTION})

    citation = response.json()["citations"][0]
    assert citation["document_id"] == str(DOCUMENT_ID_1)
    assert citation["chunk_id"] == str(CHUNK_ID_1)


@pytest.mark.parametrize("question", ["", "   "])
def test_blank_question_returns_422(client: TestClient, question: str) -> None:
    response = client.post("/ask", json={"question": question})

    assert response.status_code == 422


def test_missing_question_returns_422(client: TestClient) -> None:
    response = client.post("/ask", json={})

    assert response.status_code == 422


def test_invalid_json_field_type_returns_422(client: TestClient) -> None:
    response = client.post("/ask", json={"question": 123})

    assert response.status_code == 422


def test_unavailable_service_maps_to_503(client: TestClient) -> None:
    app.dependency_overrides[askme.get_askme_service] = lambda: RaisingService(
        AskMeUnavailableError("internal provider detail")
    )

    response = client.post("/ask", json={"question": QUESTION})

    assert response.status_code == 503
    assert response.json() == {"detail": "AskMe is temporarily unavailable."}


def test_grounding_error_maps_to_502(client: TestClient) -> None:
    app.dependency_overrides[askme.get_askme_service] = lambda: RaisingService(
        AskMeGroundingError("internal evidence detail")
    )

    response = client.post("/ask", json={"question": QUESTION})

    assert response.status_code == 502
    assert response.json() == {
        "detail": "AskMe could not produce a safely grounded answer."
    }


def test_internal_exception_details_absent(client: TestClient) -> None:
    app.dependency_overrides[askme.get_askme_service] = lambda: RaisingService(
        AskMeUnavailableError("internal sensitive detail")
    )

    response = client.post("/ask", json={"question": QUESTION})

    assert "prompt" not in response.text
    assert "raw-detail" not in response.text
    assert "model" not in response.text


def test_default_unconfigured_dependency_returns_503(client: TestClient) -> None:
    response = client.post("/ask", json={"question": QUESTION})

    assert response.status_code == 503
    assert response.json() == {"detail": "AskMe is temporarily unavailable."}


def test_dependency_override_cleanup_prevents_test_leakage() -> None:
    app.dependency_overrides[askme.get_askme_service] = lambda: SuccessfulService()
    with TestClient(app) as first_client:
        assert first_client.post("/ask", json={"question": QUESTION}).status_code == 200
    app.dependency_overrides.clear()

    with TestClient(app) as second_client:
        response = second_client.post("/ask", json={"question": QUESTION})

    assert response.status_code == 503


def _citation(
    citation_id: str,
    document_id: UUID,
    filename: str,
    page_number: int,
    chunk_id: UUID,
) -> AskMeCitation:
    return AskMeCitation(
        citation_id=citation_id,
        document_id=document_id,
        filename=filename,
        page_number=page_number,
        chunk_id=chunk_id,
    )


def _result(
    *,
    question: str = QUESTION,
    answer: str = ANSWER,
    citations: tuple[AskMeCitation, ...] = (
        _citation("S1", DOCUMENT_ID_1, "refund-policy.pdf", 2, CHUNK_ID_1),
    ),
) -> AskMeResult:
    return AskMeResult(
        request_id=REQUEST_ID,
        question=question,
        answer=answer,
        citations=citations,
    )
