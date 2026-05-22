import pytest

from app.agent.schemas import RequestOptions
from app.agent.tools.registry import ToolRegistry
from app.core.config import get_settings
from app.knowledge.models import KnowledgeCitation
from app.providers.mock import (
    MockChatProvider,
    MockImageProvider,
    MockSearchProvider,
    MockVideoProvider,
)
from app.storage.attachments import AttachmentStore


class _MockKnowledgeStore:
    enabled = True

    async def search(self, user_id: str, query: str, *, top_k: int = 5) -> list[KnowledgeCitation]:
        del user_id, top_k
        return [
            KnowledgeCitation(
                index=1,
                doc_id="doc-1",
                filename="lab.md",
                chunk_index=0,
                excerpt=f"excerpt for {query}",
                score=0.12,
            ),
        ]


@pytest.mark.asyncio
async def test_search_knowledge_returns_citations(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATTACHMENTS_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()
    registry = ToolRegistry(
        search_provider=MockSearchProvider(),
        image_provider=MockImageProvider(),
        video_provider=MockVideoProvider(),
        chat_provider=MockChatProvider(),
        attachment_store=AttachmentStore(settings),
        settings=settings,
        knowledge_store=_MockKnowledgeStore(),  # type: ignore[arg-type]
    )
    result = await registry.execute(
        "search_knowledge",
        '{"query": "实验步骤"}',
        user_id="u1",
        session_id="s1",
        user_message="实验步骤是什么",
        history=[],
        options=RequestOptions(),
    )
    assert result.tool_result is not None
    assert result.tool_result.type == "knowledge"
    citations = result.tool_result.metadata.get("citations")
    assert isinstance(citations, list)
    assert citations[0]["filename"] == "lab.md"
    assert "[1]" in result.observation
    get_settings.cache_clear()
