from app.agent.orchestrator import AgentOrchestrator
from app.core.config import get_settings
from app.providers.mock import (
    MockChatProvider,
    MockImageProvider,
    MockSearchProvider,
    MockVideoProvider,
)
from app.storage.attachments import AttachmentStore
from app.storage.memory import InMemorySessionStore


def build_orchestrator() -> AgentOrchestrator:
    settings = get_settings()
    sessions = InMemorySessionStore()
    chat_provider = MockChatProvider()
    attachment_store = AttachmentStore(settings)
    return AgentOrchestrator(
        sessions=sessions,
        chat_provider=chat_provider,
        search_provider=MockSearchProvider(),
        image_provider=MockImageProvider(),
        video_provider=MockVideoProvider(),
        attachment_store=attachment_store,
        settings=settings,
    )
