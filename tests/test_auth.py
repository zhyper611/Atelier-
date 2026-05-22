from fastapi.testclient import TestClient


def test_register_and_login(client: TestClient) -> None:
    register = client.post(
        "/auth/register",
        json={"username": "alice", "password": "password123"},
    )
    assert register.status_code == 200
    payload = register.json()
    assert payload["token_type"] == "bearer"
    assert payload["user"]["username"] == "alice"
    assert payload["access_token"]

    duplicate = client.post(
        "/auth/register",
        json={"username": "alice", "password": "password123"},
    )
    assert duplicate.status_code == 409

    login = client.post(
        "/auth/login",
        json={"username": "alice", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]

    bad_login = client.post(
        "/auth/login",
        json={"username": "alice", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401


def test_me_requires_token(client: TestClient, auth_headers: dict[str, str]) -> None:
    unauthorized = client.get("/auth/me")
    assert unauthorized.status_code == 401

    authorized = client.get("/auth/me", headers=auth_headers)
    assert authorized.status_code == 200
    assert "username" in authorized.json()


def test_chat_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/chat",
        json={"session_id": "demo", "message": "你好"},
    )
    assert response.status_code == 401


def test_session_isolation_between_users(client: TestClient) -> None:
    user_a = client.post(
        "/auth/register",
        json={"username": "user_a", "password": "password123"},
    ).json()
    user_b = client.post(
        "/auth/register",
        json={"username": "user_b", "password": "password123"},
    ).json()

    headers_a = {"Authorization": f"Bearer {user_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {user_b['access_token']}"}
    session_id = "shared-session-id"

    chat = client.post(
        "/chat",
        json={"session_id": session_id, "message": "你好"},
        headers=headers_a,
    )
    assert chat.status_code == 200

    history_b = client.get(f"/sessions/{session_id}", headers=headers_b)
    assert history_b.status_code == 200
    assert history_b.json()["messages"] == []

    history_a = client.get(f"/sessions/{session_id}", headers=headers_a)
    assert history_a.status_code == 200
    assert len(history_a.json()["messages"]) >= 1
