import io

from fastapi.testclient import TestClient


def test_upload_and_delete_attachment(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    session_id = "attach-demo"
    response = client.post(
        f"/sessions/{session_id}/attachments",
        files=[("files", ("test.txt", io.BytesIO(b"hello"), "text/plain"))],
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["attachments"]) == 1
    attachment_id = payload["attachments"][0]["id"]

    delete_response = client.delete(
        f"/sessions/{session_id}/attachments/{attachment_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}


def test_upload_rejects_unsupported_mime(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/sessions/bad/attachments",
        files=[("files", ("x.exe", io.BytesIO(b"bin"), "application/octet-stream"))],
        headers=auth_headers,
    )
    assert response.status_code == 400
