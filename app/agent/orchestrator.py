import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from app.agent.planner import Planner, should_plan
from app.agent.react.loop import ReActLoop
from app.agent.schemas import AttachmentRef, ChatMessage, ChatRequest, ChatResponse, IntentType, TaskPlan
from app.providers.ark_client import humanize_provider_error
from app.agent.tools.registry import ToolRegistry
from app.knowledge.retriever import KnowledgeRetriever
from app.knowledge.store import KnowledgeStore
from app.core.config import Settings
from app.core.logging import get_logger
from app.providers.base import ChatProvider, ImageProvider, SearchProvider, VideoProvider
from app.auth.session_scope import storage_session_id_for_request
from app.storage.attachments import AttachmentStore
from app.storage.base import SessionStore

logger = get_logger(__name__)


def _run_trace_is_persistable(trace_messages: list[ChatMessage]) -> bool:
    if not trace_messages:
        return False
    return any(
        message.role == "assistant"
        and (message.content.strip() or message.tool_result is not None)
        for message in trace_messages
    )


def _resolve_attachment_refs(
    store: AttachmentStore,
    user_id: str,
    session_id: str,
    attachment_ids: list[str],
) -> list[AttachmentRef]:
    refs: list[AttachmentRef] = []
    for attachment_id in attachment_ids:
        try:
            refs.append(store.get_ref(user_id, session_id, attachment_id))
        except Exception:
            continue
    return refs


class AgentOrchestrator:
    def __init__(
        self,
        sessions: SessionStore,
        chat_provider: ChatProvider,
        search_provider: SearchProvider,
        image_provider: ImageProvider,
        video_provider: VideoProvider,
        attachment_store: AttachmentStore,
        settings: Settings,
        knowledge_store: KnowledgeStore | None = None,
        *,
        max_steps: int = 8,
        trace_observation_max_chars: int = 4000,
        tool_timeout_seconds: int = 120,
        video_tool_timeout_seconds: int = 600,
        tool_retry_max_attempts: int = 2,
    ) -> None:
        self.sessions = sessions
        self._settings = settings
        self._planner = Planner(chat_provider, settings)
        knowledge_retriever = (
            KnowledgeRetriever(knowledge_store, settings)
            if knowledge_store is not None
            else None
        )
        self._react_loop = ReActLoop(
            chat_provider=chat_provider,
            tool_registry=ToolRegistry(
                search_provider=search_provider,
                image_provider=image_provider,
                video_provider=video_provider,
                chat_provider=chat_provider,
                attachment_store=attachment_store,
                settings=settings,
                knowledge_store=knowledge_store,
            ),
            knowledge_retriever=knowledge_retriever,
            max_steps=max_steps,
            trace_observation_max_chars=trace_observation_max_chars,
            tool_timeout_seconds=tool_timeout_seconds,
            video_tool_timeout_seconds=video_tool_timeout_seconds,
            tool_retry_max_attempts=tool_retry_max_attempts,
            code_exec_timeout_seconds=settings.code_exec_timeout_seconds,
            fetch_tool_timeout_seconds=(
                settings.fetch_url_timeout_seconds * settings.fetch_url_max_urls_per_call
                + 5
            ),
            attachment_store=attachment_store,
        )

    async def _maybe_create_plan(self, request: ChatRequest) -> TaskPlan | None:
        if not should_plan(
            request.message,
            request.attachments,
            request,
            self._settings,
        ):
            return None
        try:
            return await self._planner.create_plan(request.message, request.attachments)
        except Exception as exc:
            logger.warning(
                "plan_creation_failed",
                extra={
                    "session_id": request.session_id,
                    "event": "plan_creation_failed",
                    "error": str(exc),
                },
            )
            return None

    def _error_response(
        self,
        request: ChatRequest,
        *,
        run_id: str,
        message: str,
    ) -> ChatResponse:
        return ChatResponse(
            session_id=request.session_id,
            run_id=run_id,
            intent=IntentType.CHAT,
            answer=f"抱歉，{message}",
        )

    async def handle(
        self,
        request: ChatRequest,
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> ChatResponse:
        started = time.perf_counter()
        storage_id = storage_session_id_for_request(request)
        history = await self.sessions.get(storage_id)
        plan = await self._maybe_create_plan(request)
        try:
            response, trace_messages = await self._react_loop.handle(
                request,
                history,
                plan=plan,
                cancel_event=cancel_event,
            )
            if cancel_event is None or not cancel_event.is_set():
                await self._persist_run(request, trace_messages)
            return response
        except Exception as exc:
            logger.exception(
                "chat_failed",
                extra={"session_id": request.session_id, "event": "chat_failed"},
            )
            return self._error_response(
                request,
                run_id=str(uuid4()),
                message=humanize_provider_error(exc),
            )
        except asyncio.CancelledError:
            logger.info(
                "chat_cancelled",
                extra={
                    "session_id": request.session_id,
                    "event": "chat_cancelled",
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                },
            )
            raise
        finally:
            logger.info(
                "chat_completed",
                extra={
                    "session_id": request.session_id,
                    "event": "chat_completed",
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                },
            )

    async def stream_events(
        self,
        request: ChatRequest,
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        started = time.perf_counter()
        storage_id = storage_session_id_for_request(request)
        history = await self.sessions.get(storage_id)
        run_id = str(uuid4())

        final_response: ChatResponse | None = None
        trace_messages: list[ChatMessage] = []

        try:
            plan = await self._maybe_create_plan(request)
            if plan is not None:
                yield {
                    "event": "plan_created",
                    "data": {
                        "run_id": run_id,
                        "plan": plan.model_dump(mode="json"),
                    },
                }

            async for event in self._react_loop.stream_events(
                request,
                history,
                plan=plan,
                cancel_event=cancel_event,
            ):
                if event.get("event") == "final":
                    data = dict(event.get("data") or {})
                    trace_raw = data.pop("_trace_messages", [])
                    trace_messages = [ChatMessage.model_validate(item) for item in trace_raw]
                    client_data = {
                        key: value for key, value in data.items() if key != "_trace_messages"
                    }
                    final_response = ChatResponse.model_validate(client_data)
                    yield {"event": "final", "data": client_data}
                    continue
                yield event

            if final_response is not None and (cancel_event is None or not cancel_event.is_set()):
                await self._persist_run(request, trace_messages)
        except asyncio.CancelledError:
            logger.info(
                "stream_cancelled",
                extra={
                    "session_id": request.session_id,
                    "event": "stream_cancelled",
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                },
            )
            raise
        except Exception as exc:
            logger.exception(
                "stream_failed",
                extra={"session_id": request.session_id, "event": "stream_failed"},
            )
            message = humanize_provider_error(exc)
            error_response = self._error_response(
                request,
                run_id=run_id,
                message=message,
            )
            yield {
                "event": "error",
                "data": {"run_id": run_id, "message": message},
            }
            yield {
                "event": "final",
                "data": error_response.model_dump(mode="json"),
            }
        finally:
            logger.info(
                "stream_completed",
                extra={
                    "session_id": request.session_id,
                    "event": "stream_completed",
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                },
            )

    async def _persist_run(
        self,
        request: ChatRequest,
        trace_messages: list[ChatMessage],
    ) -> None:
        if not _run_trace_is_persistable(trace_messages):
            return
        attachment_refs = (
            _resolve_attachment_refs(
                self._react_loop.attachment_store,
                request.user_id or "",
                request.session_id,
                request.attachments,
            )
            if self._react_loop.attachment_store and request.user_id
            else []
        )

        user_message = ChatMessage(
            role="user",
            content=request.message,
            attachments=attachment_refs,
        )
        await self.sessions.append_many(
            storage_session_id_for_request(request),
            [user_message, *trace_messages],
        )
