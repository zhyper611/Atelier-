import httpx
import pytest

from app.agent.react.schemas import ToolCallRequest
from app.agent.schemas import RequestOptions
from app.agent.tools.executor import ToolExecutionContext, execute_tool_calls
from app.agent.tools.registry import ToolRegistry
from app.core.config import Settings
from app.providers.mock import (
    MockChatProvider,
    MockImageProvider,
    MockSearchProvider,
    MockVideoProvider,
)
from app.storage.attachments import AttachmentStore

SAMPLE_HTML = """
<html><head><title>Registry Test</title></head>
<body><article><p>Full article body for registry test.</p></article></body>
</html>
"""


def _build_registry(settings: Settings) -> ToolRegistry:
    return ToolRegistry(
        search_provider=MockSearchProvider(),
        image_provider=MockImageProvider(),
        video_provider=MockVideoProvider(),
        chat_provider=MockChatProvider(),
        attachment_store=AttachmentStore(settings),
        settings=settings,
    )


@pytest.mark.asyncio
async def test_registry_fetch_url_with_mock_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(fetch_url_enabled=True)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SAMPLE_HTML, headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)

    async def mock_fetch_urls(urls, s):
        from app.agent.tools import url_fetcher

        async with httpx.AsyncClient(transport=transport) as client:
            return [
                await url_fetcher.fetch_and_extract(url, s, client=client) for url in urls
            ]

    monkeypatch.setattr(
        "app.agent.tools.registry.fetch_urls",
        mock_fetch_urls,
    )

    registry = _build_registry(settings)
    context = ToolExecutionContext(
        user_id="test-user",
        session_id="test-session",
        user_message="read",
        history=[],
        options=RequestOptions(),
        use_knowledge_base=False,
    )
    outcomes = await execute_tool_calls(
        registry,
        [
            ToolCallRequest(
                id="1",
                name="fetch_url",
                arguments='{"urls":["https://news.example.com/a"]}',
            ),
        ],
        context=context,
        fetch_tool_timeout_seconds=30.0,
        max_attempts=1,
    )

    observation = outcomes[0].execution.observation
    assert "Registry Test" in observation or "article body" in observation
    assert outcomes[0].execution.tool_result is not None
    assert outcomes[0].execution.tool_result.type == "fetch"
