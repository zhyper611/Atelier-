import pytest

from app.agent.planner import Planner, is_simple_media_analysis_request, should_plan
from app.agent.schemas import ChatRequest, RequestOptions
from app.core.config import get_settings
from app.providers.mock import MockChatProvider


def test_should_plan_on_long_message() -> None:
    settings = get_settings()
    request = ChatRequest(message="x" * 80)
    assert should_plan(request.message, [], request, settings) is True


def test_is_simple_media_analysis_request() -> None:
    assert is_simple_media_analysis_request("描述图片内容") is True
    assert is_simple_media_analysis_request("帮我做一份完整的求职方案") is False


def test_should_plan_skips_simple_image_with_attachment() -> None:
    settings = get_settings()
    request = ChatRequest(message="描述图片内容")
    assert should_plan(request.message, ["att-1"], request, settings) is False


def test_should_plan_off_mode() -> None:
    settings = get_settings()
    request = ChatRequest(
        message="帮我做一份完整的求职方案包括简历和面试",
        options=RequestOptions(planning_mode="off"),
    )
    assert should_plan(request.message, [], request, settings) is False


@pytest.mark.asyncio
async def test_planner_create_plan_mock() -> None:
    settings = get_settings()
    planner = Planner(MockChatProvider(), settings)
    plan = await planner.create_plan("帮我做求职方案", [])
    assert plan.goal
    assert len(plan.steps) >= 3
