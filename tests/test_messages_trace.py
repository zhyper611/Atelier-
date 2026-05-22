from app.agent.react.messages import (
    build_initial_messages,
    collapse_messages_for_streaming_completion,
    history_item_to_working_message,
    normalize_messages_for_api,
    truncate_observation,
)
from app.agent.schemas import ChatMessage


def test_truncate_observation() -> None:
    assert truncate_observation("hello", 10) == "hello"
    assert truncate_observation("abcdefghij", 7) == "abcd..."


def test_history_item_replays_tool_calls_and_tool_role() -> None:
    assistant_tools = history_item_to_working_message(
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "web_search", "arguments": "{}"},
                },
            ],
        ),
    )
    assert assistant_tools is not None
    assert assistant_tools["role"] == "assistant"
    assert len(assistant_tools["tool_calls"]) == 1

    tool_msg = history_item_to_working_message(
        ChatMessage(
            role="tool",
            content="搜索摘要",
            tool_call_id="call_1",
        ),
    )
    assert tool_msg == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "搜索摘要",
    }


def test_build_initial_messages_includes_full_trace() -> None:
    history = [
        ChatMessage(role="user", content="今天新闻"),
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "web_search", "arguments": '{"query":"AI"}'},
                },
            ],
        ),
        ChatMessage(role="tool", content="摘要内容", tool_call_id="c1"),
        ChatMessage(role="assistant", content="今日 AI 新闻如下。"),
    ]

    messages = build_initial_messages(history, "再总结一下")

    roles = [m["role"] for m in messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant", "user"]
    assert messages[3]["tool_call_id"] == "c1"


def test_build_initial_messages_includes_identity_mask() -> None:
    from app.core.config import Settings

    messages = build_initial_messages(
        [],
        "你好",
        settings=Settings(agent_identity_mask_doubao=True),
    )
    assert messages[0]["role"] == "system"
    assert "你不是豆包" in messages[0]["content"]


def test_build_initial_messages_merges_plan_into_single_system() -> None:
    messages = build_initial_messages(
        [],
        "描述图片",
        plan_prompt="当前任务计划：识图\n请按步骤推进。",
    )
    assert sum(1 for m in messages if m["role"] == "system") == 1
    assert "当前任务计划" in messages[0]["content"]


def test_collapse_messages_for_streaming_removes_tool_roles() -> None:
    raw = [
        {"role": "system", "content": "规则"},
        {"role": "user", "content": "今天 AI 新闻？"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "web_search"}}],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "搜索摘要"},
    ]
    collapsed = collapse_messages_for_streaming_completion(raw)
    roles = [m["role"] for m in collapsed]
    assert "tool" not in roles
    assert roles.count("user") >= 2
    assert "搜索摘要" in collapsed[-1]["content"]


def test_normalize_messages_for_api_merges_leading_system() -> None:
    raw = [
        {"role": "system", "content": "A"},
        {"role": "system", "content": "B"},
        {"role": "user", "content": "hi"},
    ]
    normalized = normalize_messages_for_api(raw)
    assert normalized[0]["role"] == "system"
    assert "A" in normalized[0]["content"]
    assert "B" in normalized[0]["content"]
    assert normalized[1]["role"] == "user"
