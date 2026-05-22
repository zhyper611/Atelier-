import asyncio
import contextlib
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.agent.orchestrator import AgentOrchestrator
from app.agent.schemas import (
    AttachmentUploadResponse,
    ChatRequest,
    ChatResponse,
    SessionHistoryResponse,
)
from app.storage.attachments import AttachmentStore
from app.api.deps import check_rate_limit, get_current_user, verify_api_key
from app.auth.session_scope import storage_session_id
from app.auth.user_store import UserRecord
from app.core.config import get_settings


def _get_orchestrator(request: Request) -> AgentOrchestrator:
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise RuntimeError("Agent orchestrator is not initialized")
    return orchestrator


def _get_attachment_store(request: Request) -> AttachmentStore:
    store = getattr(request.app.state, "attachment_store", None)
    if store is None:
        raise RuntimeError("Attachment store is not initialized")
    return store


def _bind_user_request(body: ChatRequest, user: UserRecord) -> ChatRequest:
    return body.model_copy(update={"user_id": user.id})


async def _run_ready_checks(request: Request) -> dict[str, object]:
    settings = get_settings()
    checks: dict[str, str] = {"app": "ok"}

    if settings.session_store == "redis":
        redis_client = getattr(request.app.state, "redis_client", None)
        if redis_client is None:
            checks["redis"] = "not_configured"
        else:
            try:
                await redis_client.ping()
                checks["redis"] = "ok"
            except Exception as exc:
                checks["redis"] = f"error: {exc}"
    else:
        checks["redis"] = "skipped"

    if settings.llm_api_base_url and settings.llm_api_key:
        checks["llm"] = "configured"
    else:
        checks["llm"] = "mock_or_unconfigured"

    if settings.knowledge_enabled:
        knowledge_store = getattr(request.app.state, "knowledge_store", None)
        if knowledge_store is None:
            checks["knowledge"] = "unavailable"
        else:
            try:
                ok = await knowledge_store.ping()
                checks["knowledge"] = "ok" if ok else "degraded"
            except Exception as exc:
                checks["knowledge"] = f"error: {exc}"
    else:
        checks["knowledge"] = "disabled"

    status = "ok" if all(value == "ok" or value in {"skipped", "configured", "mock_or_unconfigured", "disabled"} for value in checks.values()) else "degraded"
    if checks.get("redis", "").startswith("error"):
        status = "unavailable"
    return {"status": status, "checks": checks}


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/health/ready")
    async def health_ready(request: Request) -> dict[str, object]:
        payload = await _run_ready_checks(request)
        if payload["status"] == "unavailable":
            raise HTTPException(status_code=503, detail=payload)
        return payload

    @router.post("/chat", response_model=ChatResponse)
    async def chat(
        body: ChatRequest,
        request: Request,
        orchestrator: AgentOrchestrator = Depends(_get_orchestrator),
        current_user: UserRecord = Depends(get_current_user),
        _: None = Depends(verify_api_key),
    ) -> ChatResponse:
        client_session_id = body.session_id
        await check_rate_limit(request, f"user:{current_user.id}")
        internal = _bind_user_request(body, current_user)
        response = await orchestrator.handle(internal)
        return response.model_copy(update={"session_id": client_session_id})

    @router.post("/chat/stream")
    async def chat_stream(
        body: ChatRequest,
        request: Request,
        orchestrator: AgentOrchestrator = Depends(_get_orchestrator),
        current_user: UserRecord = Depends(get_current_user),
        _: None = Depends(verify_api_key),
    ) -> StreamingResponse:
        client_session_id = body.session_id
        await check_rate_limit(request, f"user:{current_user.id}")
        internal = _bind_user_request(body, current_user)
        cancel_event = asyncio.Event()

        async def watch_disconnect() -> None:
            while True:
                if await request.is_disconnected():
                    cancel_event.set()
                    return
                await asyncio.sleep(0.2)

        async def event_stream() -> AsyncIterator[str]:
            watcher = asyncio.create_task(watch_disconnect())
            try:
                async for event in orchestrator.stream_events(internal, cancel_event=cancel_event):
                    if cancel_event.is_set():
                        break
                    if event.get("event") == "final":
                        data = dict(event.get("data") or {})
                        data["session_id"] = client_session_id
                        yield _format_sse_event({"event": "final", "data": data})
                        continue
                    yield _format_sse_event(event)
            except asyncio.CancelledError:
                pass
            finally:
                watcher.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await watcher

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
    async def read_session(
        session_id: str,
        request: Request,
        orchestrator: AgentOrchestrator = Depends(_get_orchestrator),
        current_user: UserRecord = Depends(get_current_user),
        _: None = Depends(verify_api_key),
    ) -> SessionHistoryResponse:
        await check_rate_limit(request, f"user:{current_user.id}")
        scoped = storage_session_id(current_user.id, session_id)
        return SessionHistoryResponse(
            session_id=session_id,
            messages=await orchestrator.sessions.get(scoped),
        )

    @router.delete("/sessions/{session_id}")
    async def delete_session(
        session_id: str,
        request: Request,
        orchestrator: AgentOrchestrator = Depends(_get_orchestrator),
        current_user: UserRecord = Depends(get_current_user),
        _: None = Depends(verify_api_key),
    ) -> dict[str, bool]:
        await check_rate_limit(request, f"user:{current_user.id}")
        scoped = storage_session_id(current_user.id, session_id)
        return {"deleted": await orchestrator.sessions.clear(scoped)}

    @router.post(
        "/sessions/{session_id}/attachments",
        response_model=AttachmentUploadResponse,
    )
    async def upload_attachments(
        session_id: str,
        request: Request,
        files: list[UploadFile] = File(...),
        store: AttachmentStore = Depends(_get_attachment_store),
        current_user: UserRecord = Depends(get_current_user),
        _: None = Depends(verify_api_key),
    ) -> AttachmentUploadResponse:
        await check_rate_limit(request, f"user:{current_user.id}")
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        refs = []
        for upload in files:
            refs.append(
                await store.save_upload(current_user.id, session_id, upload),
            )
        return AttachmentUploadResponse(attachments=refs)

    @router.delete("/sessions/{session_id}/attachments/{attachment_id}")
    async def delete_attachment(
        session_id: str,
        attachment_id: str,
        request: Request,
        store: AttachmentStore = Depends(_get_attachment_store),
        current_user: UserRecord = Depends(get_current_user),
        _: None = Depends(verify_api_key),
    ) -> dict[str, bool]:
        await check_rate_limit(request, f"user:{current_user.id}")
        return {
            "deleted": store.delete(current_user.id, session_id, attachment_id),
        }

    return router


def _format_sse_event(event: dict[str, object]) -> str:
    event_name = event["event"]
    data = json.dumps(event["data"], ensure_ascii=False)
    return f"event: {event_name}\ndata: {data}\n\n"
