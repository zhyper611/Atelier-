import pytest

from app.agent.react.loop import _select_tool_calls_for_step
from app.agent.react.schemas import ToolCallRequest


def test_select_tool_calls_defers_media_when_search_in_same_turn() -> None:
    calls = [
        ToolCallRequest(id="1", name="generate_image", arguments='{"prompt":"海报"}'),
        ToolCallRequest(id="2", name="web_search", arguments='{"query":"新闻"}'),
    ]

    execute, deferred = _select_tool_calls_for_step(calls)

    assert len(execute) == 1
    assert execute[0].name == "web_search"
    assert len(deferred) == 1
    assert deferred[0].name == "generate_image"


def test_select_tool_calls_defers_fetch_when_search_in_same_turn() -> None:
    calls = [
        ToolCallRequest(id="1", name="fetch_url", arguments='{"urls":["https://a.com"]}'),
        ToolCallRequest(id="2", name="web_search", arguments='{"query":"研报"}'),
    ]

    execute, deferred = _select_tool_calls_for_step(calls)

    assert len(execute) == 1
    assert execute[0].name == "web_search"
    assert len(deferred) == 1
    assert deferred[0].name == "fetch_url"


def test_select_tool_calls_keeps_single_media_tool() -> None:
    calls = [
        ToolCallRequest(id="1", name="generate_image", arguments='{"prompt":"海报"}'),
    ]

    execute, deferred = _select_tool_calls_for_step(calls)

    assert execute == calls
    assert deferred == []
