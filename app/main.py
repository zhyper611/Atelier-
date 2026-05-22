import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agent.orchestrator import AgentOrchestrator
from app.api.rate_limit import build_rate_limiter
from app.api.routes import build_router
from app.auth.routes import build_auth_router
from app.auth.user_store import UserStore
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.providers.factory import (
    build_chat_provider,
    build_image_provider,
    build_search_provider,
    build_video_provider,
)
from app.knowledge.factory import build_knowledge_store, close_knowledge_store
from app.knowledge.routes import build_knowledge_router
from app.storage.attachments import AttachmentStore
from app.storage.factory import session_store_lifespan


def _build_orchestrator(
    settings: Settings,
    sessions,
    attachment_store: AttachmentStore,
    knowledge_store,
) -> AgentOrchestrator:
    chat_provider = build_chat_provider(settings)
    return AgentOrchestrator(
        sessions=sessions,
        chat_provider=chat_provider,
        search_provider=build_search_provider(settings),
        image_provider=build_image_provider(settings),
        video_provider=build_video_provider(settings),
        attachment_store=attachment_store,
        knowledge_store=knowledge_store,
        settings=settings,
        max_steps=settings.agent_max_steps,
        trace_observation_max_chars=settings.trace_observation_max_chars,
        tool_timeout_seconds=settings.tool_timeout_seconds,
        video_tool_timeout_seconds=settings.video_tool_timeout_seconds,
        tool_retry_max_attempts=settings.tool_retry_max_attempts,
    )


def _warn_insecure_jwt_secret(settings: Settings) -> None:
    if not settings.auth_enabled:
        return
    if settings.jwt_secret != "change-me-in-production":
        return
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    logging.getLogger(__name__).warning(
        "JWT_SECRET 仍为默认值 change-me-in-production；请在 .env 中设置至少 32 字符的随机密钥。"
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(structured=settings.enable_structured_logs)
    _warn_insecure_jwt_secret(settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        user_store = UserStore(settings.users_db_path)
        await user_store.open()
        application.state.user_store = user_store
        knowledge_store = await build_knowledge_store(settings)
        application.state.knowledge_store = knowledge_store
        try:
            async with session_store_lifespan(settings) as (sessions, redis_client):
                application.state.redis_client = redis_client
                application.state.attachment_store = AttachmentStore(settings)
                application.state.rate_limiter = await build_rate_limiter(
                    session_store=settings.session_store,
                    redis_url=settings.redis_url,
                    max_requests=settings.rate_limit_requests,
                    window_seconds=settings.rate_limit_window_seconds,
                )
                application.state.orchestrator = _build_orchestrator(
                    settings,
                    sessions,
                    application.state.attachment_store,
                    knowledge_store,
                )
                try:
                    yield
                finally:
                    await application.state.rate_limiter.close()
        finally:
            await close_knowledge_store(knowledge_store)
            await user_store.close()

    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.include_router(build_auth_router())
    application.include_router(build_router())
    application.include_router(build_knowledge_router())
    return application


app = create_app()
