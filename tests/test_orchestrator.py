import pytest

from app.agent.schemas import ChatRequest, IntentType, RequestOptions
from tests.helpers import build_orchestrator


@pytest.mark.asyncio
async def test_orchestrator_calls_image_provider_for_image_requests() -> None:
    orchestrator = build_orchestrator()
    request = ChatRequest(session_id="demo", message="画一张 1024x768 的猫咪头像")

    response = await orchestrator.handle(request)

    assert response.intent == IntentType.IMAGE
    assert response.run_id
    assert response.tool_result is not None
    assert response.tool_result.type == "image"
    assert response.tool_result.metadata["size"] == "1024x768"


@pytest.mark.asyncio
async def test_orchestrator_uses_search_before_answering_timely_questions() -> None:
    orchestrator = build_orchestrator()
    request = ChatRequest(session_id="demo", message="今天有哪些科技新闻？")

    response = await orchestrator.handle(request)

    assert response.intent == IntentType.SEARCH
    assert response.tool_result is not None
    assert response.tool_result.type == "search"
    assert "搜索" in response.answer
    assert len(response.steps) >= 1


@pytest.mark.asyncio
async def test_orchestrator_keeps_conversation_history_with_trace() -> None:
    orchestrator = build_orchestrator()
    request = ChatRequest(
        session_id="demo",
        message="今天有哪些科技新闻？",
        options=RequestOptions(default_image_size="800x800"),
    )

    await orchestrator.handle(request)

    history = await orchestrator.sessions.get("demo")
    roles = [message.role for message in history]
    assert roles[0] == "user"
    assert "assistant" in roles
    assert "tool" in roles
    final_assistant = history[-1]
    assert final_assistant.role == "assistant"
    assert final_assistant.run_id


@pytest.mark.asyncio
async def test_orchestrator_persists_image_tool_result_in_history() -> None:
    orchestrator = build_orchestrator()
    request = ChatRequest(session_id="demo", message="画一张猫咪图片")

    response = await orchestrator.handle(request)

    history = await orchestrator.sessions.get("demo")
    assistant_messages = [m for m in history if m.role == "assistant"]
    assert assistant_messages
    final = assistant_messages[-1]
    assert final.tool_result is not None
    assert final.tool_result.type == "image"
    assert final.tool_result.url == response.tool_result.url


@pytest.mark.asyncio
async def test_orchestrator_uses_previous_image_for_follow_up_video() -> None:
    orchestrator = build_orchestrator()
    image_request = ChatRequest(session_id="demo", message="画一张猫咪图片")
    await orchestrator.handle(image_request)

    video_request = ChatRequest(
        session_id="demo",
        message="根据刚才生成的图片生成一段 5 秒视频",
    )
    response = await orchestrator.handle(video_request)

    assert response.intent == IntentType.VIDEO
    assert response.tool_result is not None
    assert response.tool_result.metadata["mode"] == "image_to_video"
    assert response.tool_result.metadata["reference_image_url"] is not None


@pytest.mark.asyncio
async def test_orchestrator_does_not_create_session_before_successful_run() -> None:
    orchestrator = build_orchestrator()
    history = await orchestrator.sessions.get("unused-session")
    assert history == []


@pytest.mark.asyncio
async def test_orchestrator_creates_plan_for_complex_request() -> None:
    orchestrator = build_orchestrator()
    request = ChatRequest(
        session_id="plan-demo",
        message="帮我做一份完整的求职方案，包括岗位分析、简历、面试话术和复盘步骤",
    )

    response = await orchestrator.handle(request)

    assert response.plan is not None
    assert len(response.plan.steps) >= 3


@pytest.mark.asyncio
async def test_orchestrator_video_uses_session_image_on_short_follow_up() -> None:
    orchestrator = build_orchestrator()
    await orchestrator.handle(ChatRequest(session_id="demo", message="画一只猫"))
    response = await orchestrator.handle(
        ChatRequest(session_id="demo", message="做成视频"),
    )

    assert response.tool_result is not None
    assert response.tool_result.metadata["mode"] == "image_to_video"
