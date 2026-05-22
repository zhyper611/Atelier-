from __future__ import annotations

from app.agent.schemas import ChatRequest


def scoped_session_id(user_id: str, session_id: str) -> str:
    return f"{user_id}:{session_id}"


def storage_session_id(user_id: str | None, session_id: str) -> str:
    if user_id:
        return scoped_session_id(user_id, session_id)
    return session_id


def storage_session_id_for_request(request: ChatRequest) -> str:
    return storage_session_id(request.user_id, request.session_id)
