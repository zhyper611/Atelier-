import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def _test_settings(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("API_KEY", "")
    monkeypatch.setenv("SESSION_STORE", "memory")
    monkeypatch.setenv("KNOWLEDGE_ENABLED", "false")
    monkeypatch.setenv("USE_MOCK_PROVIDERS", "true")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("USERS_DB_PATH", str(tmp_path / "users.db"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client) -> dict[str, str]:
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/auth/register",
        json={"username": username, "password": "password123"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
