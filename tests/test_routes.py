from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert "checks" in payload


def test_chat_endpoint_returns_image_tool_result(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/chat",
        json={
            "session_id": "route-demo",
            "message": "帮我生成一张 16:9 的城市图片",
            "options": {"default_image_size": "1024x576"},
        },
        headers=auth_headers,
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["intent"] == "image"
    assert payload["run_id"]
    assert payload["tool_result"]["type"] == "image"
    assert payload["tool_result"]["metadata"]["size"] == "1024x576"


def test_session_read_and_delete_endpoints(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    client.post(
        "/chat",
        json={"session_id": "session-demo", "message": "你好"},
        headers=auth_headers,
    )

    read_response = client.get("/sessions/session-demo", headers=auth_headers)
    assert read_response.status_code == 200
    assert len(read_response.json()["messages"]) == 2

    delete_response = client.delete("/sessions/session-demo", headers=auth_headers)
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}


def test_stream_endpoint_returns_sse_events(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    with client.stream(
        "POST",
        "/chat/stream",
        json={"session_id": "stream-demo", "message": "今天有什么 AI 新闻？"},
        headers=auth_headers,
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: run_started" in body
    assert "event: step_started" in body
    assert "event: final" in body
    assert "_trace_messages" not in body
