from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from loreforge.api import admin
from loreforge.application import CompositionFactories, create_application_container
from loreforge.documents.upload import PDF_MEDIA_TYPE
from loreforge.embeddings import EmbeddingRequest, EmbeddingResult, EmbeddingVector
from loreforge.generation.models import GenerationRequest, GenerationResponse
from loreforge.main import create_app
from loreforge.reranking import RerankingRequest, RerankingScore

DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000501")
QUESTION = "Which retrieval methods does LoreForge combine?"
ANSWER = "LoreForge combines semantic vector search with BM25 lexical search [S1]."
PDF_TEXT = (
    "LoreForge combines semantic vector search with BM25 lexical search. "
    "The results are merged through reciprocal rank fusion and then reranked."
)
PDF_FILENAME = "loreforge-retrieval.pdf"
UPLOADED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


class DeterministicEmbeddingProvider:
    def __init__(self, *, fail_documents: bool = False) -> None:
        self.fail_documents = fail_documents
        self.document_requests: list[tuple[EmbeddingRequest, ...]] = []
        self.query_questions: list[str] = []

    def embed(self, requests: tuple[EmbeddingRequest, ...]) -> EmbeddingResult:
        self.document_requests.append(requests)
        if self.fail_documents:
            raise RuntimeError("raw embedding provider detail")
        return self._result_for(requests)

    def embed_documents(
        self,
        requests: tuple[EmbeddingRequest, ...],
    ) -> EmbeddingResult:
        return self.embed(requests)

    def embed_query(self, question: str) -> EmbeddingVector:
        self.query_questions.append(question)
        return EmbeddingVector(item_id=DOCUMENT_ID, values=(1.0, 0.0))

    def _result_for(self, requests: tuple[EmbeddingRequest, ...]) -> EmbeddingResult:
        return EmbeddingResult(
            model="deterministic-test-embedding",
            dimensions=2,
            vectors=tuple(
                EmbeddingVector(item_id=request.item_id, values=(1.0, 0.0))
                for request in requests
            ),
        )


class DeterministicRerankerProvider:
    def __init__(self) -> None:
        self.requests: list[tuple[RerankingRequest, ...]] = []

    def score(
        self,
        requests: tuple[RerankingRequest, ...],
    ) -> tuple[RerankingScore, ...]:
        self.requests.append(requests)
        return tuple(
            RerankingScore(item_id=request.item_id, score=1.0) for request in requests
        )


class DeterministicLLMProvider:
    def __init__(self) -> None:
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        self.requests.append(request)
        assert PDF_TEXT in request.user_prompt
        assert "[S1]" in request.user_prompt
        assert QUESTION in request.user_prompt
        return GenerationResponse(
            text=ANSWER,
            model="deterministic-test-llm",
            finish_reason="stop",
        )


def test_end_to_end_rag_vertical_slice_through_http(
    monkeypatch,
) -> None:
    embedding_provider = DeterministicEmbeddingProvider()
    reranker_provider = DeterministicRerankerProvider()
    llm_provider = DeterministicLLMProvider()
    container = create_application_container(
        factories=_factories(
            embedding_provider=embedding_provider,
            reranker_provider=reranker_provider,
            llm_provider=llm_provider,
        )
    )
    application = create_app(container_factory=lambda: container)
    pdf_content = _build_text_pdf((PDF_TEXT,))
    monkeypatch.setattr(admin, "_new_document_id", lambda: DOCUMENT_ID)
    monkeypatch.setattr(admin, "_utc_now", lambda: UPLOADED_AT)

    with TestClient(application) as client:
        create_response = client.post(
            "/admin/documents",
            json={"filename": PDF_FILENAME, "page_count": 0, "chunk_count": 0},
        )
        assert create_response.status_code == 201
        assert create_response.json()["document_id"] == str(DOCUMENT_ID)
        assert create_response.json()["status"] == "UPLOADED"

        index_response = client.post(
            f"/admin/documents/{DOCUMENT_ID}/index",
            files={"file": (PDF_FILENAME, pdf_content, PDF_MEDIA_TYPE)},
        )
        assert index_response.status_code == 200
        assert index_response.json()["document_id"] == str(DOCUMENT_ID)
        assert index_response.json()["chunk_count"] >= 1
        assert (
            index_response.json()["semantic_indexed_count"]
            == index_response.json()["chunk_count"]
        )
        assert (
            index_response.json()["lexical_indexed_count"]
            == index_response.json()["chunk_count"]
        )

        document_response = client.get(f"/admin/documents/{DOCUMENT_ID}")
        assert document_response.status_code == 200
        assert document_response.json()["status"] == "READY"
        assert document_response.json()["page_count"] == 1
        assert (
            document_response.json()["chunk_count"]
            == index_response.json()["chunk_count"]
        )

        indexed_chunk_ids = tuple(
            request.item_id for request in embedding_provider.document_requests[0]
        )
        assert indexed_chunk_ids
        assert (
            tuple(
                chunk_id
                for chunk_id in indexed_chunk_ids
                if container.vector_index.get(chunk_id) is not None
            )
            == indexed_chunk_ids
        )
        assert (
            tuple(
                chunk_id
                for chunk_id in indexed_chunk_ids
                if container.lexical_index.get(chunk_id) is not None
            )
            == indexed_chunk_ids
        )
        assert container.query_engine is not None
        assert container.query_engine._semantic_retriever is container.vector_index
        assert container.query_engine._lexical_retriever is container.lexical_index

        ask_response = client.post("/ask", json={"question": QUESTION})

    assert ask_response.status_code == 200
    body = ask_response.json()
    assert body["question"] == QUESTION
    assert body["answer"] == ANSWER
    assert "semantic vector search" in body["answer"]
    assert "BM25 lexical search" in body["answer"]
    assert body["citations"]
    assert body["citations"][0]["citation_id"] == "S1"
    assert body["citations"][0]["document_id"] == str(DOCUMENT_ID)
    assert body["citations"][0]["filename"] == PDF_FILENAME
    assert body["citations"][0]["page_number"] == 1
    assert body["citations"][0]["chunk_id"] in tuple(
        str(chunk_id) for chunk_id in indexed_chunk_ids
    )
    assert embedding_provider.query_questions == [QUESTION]
    assert reranker_provider.requests
    assert llm_provider.requests
    assert PDF_TEXT in llm_provider.requests[0].user_prompt


def test_indexing_failure_marks_document_failed_and_leaves_indexes_empty(
    monkeypatch,
) -> None:
    embedding_provider = DeterministicEmbeddingProvider(fail_documents=True)
    container = create_application_container(
        factories=_factories(
            embedding_provider=embedding_provider,
            reranker_provider=DeterministicRerankerProvider(),
            llm_provider=DeterministicLLMProvider(),
        )
    )
    application = create_app(container_factory=lambda: container)
    pdf_content = _build_text_pdf((PDF_TEXT,))
    monkeypatch.setattr(admin, "_new_document_id", lambda: DOCUMENT_ID)
    monkeypatch.setattr(admin, "_utc_now", lambda: UPLOADED_AT)

    with TestClient(application) as client:
        create_response = client.post(
            "/admin/documents",
            json={"filename": PDF_FILENAME, "page_count": 0, "chunk_count": 0},
        )
        assert create_response.status_code == 201

        index_response = client.post(
            f"/admin/documents/{DOCUMENT_ID}/index",
            files={"file": (PDF_FILENAME, pdf_content, PDF_MEDIA_TYPE)},
        )
        document_response = client.get(f"/admin/documents/{DOCUMENT_ID}")

    assert index_response.status_code == 503
    assert index_response.json() == {
        "detail": "document indexing is temporarily unavailable"
    }
    assert "raw embedding provider detail" not in index_response.text
    assert document_response.status_code == 200
    assert document_response.json()["status"] == "FAILED"
    assert container.vector_index.size == 0
    assert container.lexical_index.size == 0


def _factories(
    *,
    embedding_provider: DeterministicEmbeddingProvider,
    reranker_provider: DeterministicRerankerProvider,
    llm_provider: DeterministicLLMProvider,
) -> CompositionFactories:
    return CompositionFactories(
        document_embedding_provider_factory=lambda: embedding_provider,
        query_embedding_provider_factory=lambda: embedding_provider,
        reranker_provider_factory=lambda: reranker_provider,
        llm_provider_factory=lambda: llm_provider,
    )


def _build_text_pdf(page_texts: tuple[str, ...]) -> bytes:
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        _pages_object(len(page_texts)),
    ]

    font_object_number = 3 + len(page_texts)
    first_content_object_number = font_object_number + 1

    for index, _text in enumerate(page_texts, start=1):
        content_object_number = first_content_object_number + index - 1
        objects.append(_page_object(content_object_number, font_object_number))

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for text in page_texts:
        objects.append(_content_stream(text))

    return _serialize_pdf(objects)


def _pages_object(page_count: int) -> bytes:
    kids = " ".join(f"{number} 0 R" for number in range(3, 3 + page_count))
    return f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode("ascii")


def _page_object(content_object_number: int, font_object_number: int) -> bytes:
    return (
        b"<< /Type /Page /Parent 2 0 R /Resources "
        + f"<< /Font << /F1 {font_object_number} 0 R >> >> ".encode("ascii")
        + b"/MediaBox [0 0 612 792] "
        + f"/Contents {content_object_number} 0 R >>".encode("ascii")
    )


def _content_stream(text: str) -> bytes:
    content = (f"BT\n/F1 24 Tf\n72 720 Td\n({_escape_pdf_text(text)}) Tj\nET\n").encode(
        "ascii"
    )
    return (
        b"<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"endstream"
    )


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _serialize_pdf(objects: list[bytes]) -> bytes:
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]

    for object_number, payload in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode("ascii"))
        pdf.extend(payload)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)
