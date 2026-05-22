import asyncio

import pytest

from app.agent.react.schemas import ToolCallRequest
from app.agent.schemas import ChatRequest, RequestOptions
from app.agent.tools.executor import ToolExecutionContext, execute_tool_calls
from app.agent.tools.registry import ToolRegistry
from app.core.config import get_settings
from app.providers.mock import (
    MockChatProvider,
    MockImageProvider,
    MockSearchProvider,
    MockVideoProvider,
)
from app.storage.attachments import AttachmentStore


def _build_registry() -> ToolRegistry:
    settings = get_settings()
    return ToolRegistry(
        search_provider=MockSearchProvider(),
        image_provider=MockImageProvider(),
        video_provider=MockVideoProvider(),
        chat_provider=MockChatProvider(),
        attachment_store=AttachmentStore(settings),
        settings=settings,
    )


class SlowSearchProvider(MockSearchProvider):
    def __init__(self, delay: float) -> None:
        self._delay = delay

    async def search(self, query: str):
        await asyncio.sleep(self._delay)
        return await super().search(query)


@pytest.mark.asyncio
async def test_execute_tool_calls_parallel() -> None:
    registry = _build_registry()
    calls = [
        ToolCallRequest(id="1", name="web_search", arguments='{"query":"a"}'),
        ToolCallRequest(id="2", name="web_search", arguments='{"query":"b"}'),
    ]
    context = ToolExecutionContext(
        user_id="test-user",
        session_id="test-session",
        user_message="news",
        history=[],
        options=RequestOptions(),
        use_knowledge_base=False,
    )

    outcomes = await execute_tool_calls(
        registry,
        calls,
        context=context,
        tool_timeout_seconds=30.0,
        max_attempts=1,
    )

    assert len(outcomes) == 2
    assert all("搜索查询" in outcome.execution.observation for outcome in outcomes)


@pytest.mark.asyncio
async def test_execute_tool_calls_timeout() -> None:
    settings = get_settings()
    registry = ToolRegistry(
        search_provider=SlowSearchProvider(delay=0.2),
        image_provider=MockImageProvider(),
        video_provider=MockVideoProvider(),
        chat_provider=MockChatProvider(),
        attachment_store=AttachmentStore(settings),
        settings=settings,
    )
    calls = [
        ToolCallRequest(id="1", name="web_search", arguments='{"query":"slow"}'),
    ]
    context = ToolExecutionContext(
        user_id="test-user",
        session_id="test-session",
        user_message="slow",
        history=[],
        options=RequestOptions(),
        use_knowledge_base=False,
    )

    outcomes = await execute_tool_calls(
        registry,
        calls,
        context=context,
        tool_timeout_seconds=0.05,
        max_attempts=1,
    )

    assert outcomes[0].execution.observation.startswith("工具执行失败")
