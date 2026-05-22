import pytest
from fastapi.testclient import TestClient

from app.knowledge.models import IndexDocumentResponse, KnowledgeDocument, KnowledgeDocumentListResponse


class _RouteMockKnowledgeStore:
    enabled = True

    async def list_documents(self, user_id: str) -> list[KnowledgeDocument]:
        del user_id
        return [
            KnowledgeDocument(
                doc_id="d1",
                filename="course.pdf",
                chunk_count=3,
                size_bytes=100,
                created_at="2026-01-01T00:00:00+00:00",
            ),
        ]

    async def index_bytes(self, user_id: str, filename: str, data: bytes, mime: str, **kwargs):
        del user_id, data, mime, kwargs
        return IndexDocumentResponse(doc_id="new-id", filename=filename, chunk_count=2)

    async def delete_document(self, user_id: str, doc_id: str) -> bool:
        del user_id
        return doc_id == "d1"


@pytest.fixture
def client_with_kb(client: TestClient) -> TestClient:
    client.app.state.knowledge_store = _RouteMockKnowledgeStore()  # type: ignore[assignment]
    return client


def test_list_knowledge_documents(
    client_with_kb: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client_with_kb.get("/knowledge/documents", headers=auth_headers)
    assert response.status_code == 200
    payload = KnowledgeDocumentListResponse.model_validate(response.json())
    assert payload.documents[0].filename == "course.pdf"


def test_upload_knowledge_document(client_with_kb, auth_headers: dict[str, str]) -> None:
    response = client_with_kb.post(
        "/knowledge/documents",
        headers=auth_headers,
        files=[("files", ("notes.txt", b"chapter one", "text/plain"))],
    )
    assert response.status_code == 200
    data = response.json()
    assert data[0]["doc_id"] == "new-id"


def test_delete_knowledge_document(client_with_kb, auth_headers: dict[str, str]) -> None:
    response = client_with_kb.delete("/knowledge/documents/d1", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_upload_knowledge_document_rejects_oversized(
    client_with_kb: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATTACHMENT_MAX_BYTES", "1024")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        huge = b"x" * 2048
        response = client_with_kb.post(
            "/knowledge/documents",
            headers=auth_headers,
            files=[("files", ("big.txt", huge, "text/plain"))],
        )
        assert response.status_code == 413
    finally:
        get_settings.cache_clear()
