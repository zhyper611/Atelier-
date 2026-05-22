import pytest
from fastapi.testclient import TestClient

from app.api.rate_limit import InMemoryRateLimiter
from app.core.config import get_settings
from app.main import create_app


@pytest.mark.asyncio
async def test_in_memory_rate_limiter_blocks_over_quota() -> None:
    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)
    assert await limiter.check("s1") is True
    assert await limiter.check("s1") is True
    assert await limiter.check("s1") is False
    await limiter.close()


def test_api_key_required_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        response = client.post(
            "/chat",
            json={"session_id": "auth-demo", "message": "你好"},
        )
        assert response.status_code == 401

        ok = client.post(
            "/chat",
            json={"session_id": "auth-demo", "message": "你好"},
            headers={"X-API-Key": "secret-key"},
        )
        assert ok.status_code == 200
    get_settings.cache_clear()


def test_auth_login_rate_limit_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        first = client.post(
            "/auth/login",
            json={"username": "nobody", "password": "password123"},
        )
        second = client.post(
            "/auth/login",
            json={"username": "nobody", "password": "password123"},
        )
        assert first.status_code == 401
        assert second.status_code == 429
    get_settings.cache_clear()


def test_rate_limit_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        first = client.post("/chat", json={"session_id": "rl-demo", "message": "你好"})
        second = client.post("/chat", json={"session_id": "rl-demo", "message": "再次"})
        assert first.status_code == 200
        assert second.status_code == 429
    get_settings.cache_clear()
