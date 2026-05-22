from app.agent.schemas import ChatMessage, ToolResult
from app.agent.session_context import (
    find_latest_session_image,
    message_references_session_image,
    resolve_video_reference_image,
)


def test_message_references_session_image() -> None:
    assert message_references_session_image("请根据刚才生成的图片做一个视频")
    assert message_references_session_image("把这张图做成 5 秒视频")
    assert not message_references_session_image("生成一段海边日落短视频")


def test_find_latest_session_image() -> None:
    history = [
        ChatMessage(role="user", content="画一只猫"),
        ChatMessage(
            role="assistant",
            content="已为你生成图片。",
            tool_result=ToolResult(type="image", url="https://cdn.example.com/cat.png"),
        ),
        ChatMessage(role="user", content="再画一只狗"),
        ChatMessage(
            role="assistant",
            content="已为你生成图片。",
            tool_result=ToolResult(type="image", url="https://cdn.example.com/dog.png"),
        ),
    ]

    latest = find_latest_session_image(history)
    assert latest is not None
    assert latest.url == "https://cdn.example.com/dog.png"


def test_resolve_video_reference_image() -> None:
    history = [
        ChatMessage(role="user", content="画一只猫"),
        ChatMessage(
            role="assistant",
            content="已为你生成图片。",
            tool_result=ToolResult(type="image", url="https://cdn.example.com/cat.png"),
        ),
    ]

    resolved = resolve_video_reference_image("根据刚才的图片生成视频", history)
    assert resolved is not None
    assert resolved.url == "https://cdn.example.com/cat.png"

    assert resolve_video_reference_image("生成海边视频", history) is None
