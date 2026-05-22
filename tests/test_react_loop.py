import pytest
import httpx

from app.agent.react.loop import ReActLoop, infer_intent
from app.agent.schemas import ChatMessage, ChatRequest, IntentType, RequestOptions, ToolResult
from app.agent.tools.registry import ToolRegistry
from app.core.config import get_settings
from app.providers.mock import MockChatProvider, MockImageProvider, MockSearchProvider, MockVideoProvider
from app.storage.attachments import AttachmentStore
from tests.helpers import build_orchestrator


def build_loop() -> ReActLoop:
    orchestrator = build_orchestrator()
    return orchestrator._react_loop


@pytest.mark.asyncio
async def test_react_plain_chat_without_tools() -> None:
    loop = build_loop()
    request = ChatRequest(
        session_id="r1",
        message="你好",
        enable_planning=False,
    )

    response, trace = await loop.handle(request, [])

    assert response.intent == IntentType.CHAT
    assert response.run_id
    assert response.tool_result is None
    assert len(trace) == 1
    assert trace[0].role == "assistant"
    assert "你好" in response.answer or "你说的是" in response.answer


@pytest.mark.asyncio
async def test_react_stream_yields_multiple_deltas() -> None:
    loop = build_loop()
    request = ChatRequest(session_id="r6", message="你好，帮我想一个周末计划")
    events = [event async for event in loop.stream_events(request, [])]
    deltas = [event for event in events if event["event"] == "delta"]
    assert len(deltas) >= 2


@pytest.mark.asyncio
async def test_react_search_then_answer() -> None:
    loop = build_loop()
    request = ChatRequest(session_id="r2", message="今天有哪些科技新闻？")

    response, trace = await loop.handle(request, [])

    assert response.intent == IntentType.SEARCH
    assert response.tool_result is not None
    assert response.tool_result.type == "search"
    assert len(response.steps) >= 1
    assert any(message.role == "tool" for message in trace)


@pytest.mark.asyncio
async def test_react_generates_image() -> None:
    loop = build_loop()
    request = ChatRequest(
        session_id="r3",
        message="画一张 1024x768 的猫咪头像",
        options=RequestOptions(default_image_size="1024x1024"),
    )

    response, _trace = await loop.handle(request, [])

    assert response.intent == IntentType.IMAGE
    assert response.tool_result is not None
    assert response.tool_result.type == "image"
    assert response.tool_result.metadata["size"] == "1024x768"


@pytest.mark.asyncio
async def test_react_generates_image_when_llm_tool_routing_is_unavailable() -> None:
    class UnavailableChatProvider(MockChatProvider):
        async def complete_with_tools(self, messages, tools):
            del messages, tools
            raise httpx.ConnectError("LLM unavailable")

        async def stream_working_messages(self, messages):
            del messages
            raise httpx.ConnectError("LLM unavailable")
            yield ""  # pragma: no cover

        async def complete_working_messages(self, messages):
            del messages
            raise httpx.ConnectError("LLM unavailable")

    settings = get_settings()
    loop = ReActLoop(
        chat_provider=UnavailableChatProvider(),
        tool_registry=ToolRegistry(
            search_provider=MockSearchProvider(),
            image_provider=MockImageProvider(),
            video_provider=MockVideoProvider(),
            chat_provider=UnavailableChatProvider(),
            attachment_store=AttachmentStore(settings),
            settings=settings,
        ),
    )
    request = ChatRequest(
        session_id="r3-fallback",
        message="帮我生成一张 16:9 的赛博朋克城市图片",
        options=RequestOptions(default_image_size="1024x576"),
    )

    response, _trace = await loop.handle(request, [])

    assert response.intent == IntentType.IMAGE
    assert response.tool_result is not None
    assert response.tool_result.type == "image"
    assert response.tool_result.metadata["size"] == "1024x576"
    assert "ConnectError" not in response.answer


@pytest.mark.asyncio
async def test_react_image_then_video_with_session_image() -> None:
    loop = build_loop()
    image_response, image_trace = await loop.handle(
        ChatRequest(session_id="r4", message="画一张猫咪图片"),
        [],
    )
    assert image_response.tool_result is not None

    history = [
        ChatMessage(role="user", content="画一张猫咪图片"),
        *image_trace,
    ]

    video_response, _trace = await loop.handle(
        ChatRequest(session_id="r4", message="根据刚才生成的图片生成一段 5 秒视频"),
        history,
    )

    assert video_response.intent == IntentType.VIDEO
    assert video_response.tool_result is not None
    assert video_response.tool_result.metadata["mode"] == "image_to_video"


@pytest.mark.asyncio
async def test_react_stream_emits_run_started() -> None:
    loop = build_loop()
    request = ChatRequest(session_id="r5", message="今天有哪些科技新闻？")
    events = [event async for event in loop.stream_events(request, [])]
    event_names = [event["event"] for event in events]

    assert event_names[0] == "run_started"
    assert events[0]["data"]["run_id"]
    final_event = next(event for event in events if event["event"] == "final")
    assert final_event["data"]["run_id"]
    assert "_trace_messages" in final_event["data"]


def test_infer_intent_from_tool_result() -> None:
    assert infer_intent(ToolResult(type="image", url="https://x")) == IntentType.IMAGE
    assert infer_intent(None) == IntentType.CHAT
