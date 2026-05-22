from __future__ import annotations

import json
import uuid
from collections.abc import Sequence

from app.agent.schemas import ChatMessage, RequestOptions
from app.agent.session_context import message_references_session_image
from app.agent.tools.params import coalesce_duration, coalesce_size

IMAGE_KEYWORDS = ("画", "图片", "图像", "生成图", "海报", "头像", "壁纸", "插画", "照片")
VIDEO_KEYWORDS = ("视频", "短视频", "动画", "影片", "镜头")
SEARCH_KEYWORDS = (
    "今天",
    "现在",
    "当前",
    "最新",
    "新闻",
    "实时",
    "价格",
    "天气",
    "最近",
    "排行",
    "版本",
    "发布",
)


def _has_any(message: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in message for keyword in keywords)


def _latest_user_message(messages: Sequence[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str):
                return content
    return ""


def _current_turn_has_tool_observations(messages: Sequence[dict]) -> bool:
    last_user_index = -1
    for index, message in enumerate(messages):
        if message.get("role") == "user":
            last_user_index = index
    if last_user_index < 0:
        return False
    return any(
        message.get("role") == "tool"
        for message in messages[last_user_index + 1 :]
    )


def _history_from_messages(messages: Sequence[dict]) -> list[ChatMessage]:
    history: list[ChatMessage] = []
    for message in messages:
        role = message.get("role")
        if role == "user":
            content = message.get("content")
            if isinstance(content, str):
                history.append(ChatMessage(role="user", content=content))
        elif role == "assistant" and message.get("tool_calls"):
            continue
        elif role == "assistant":
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                history.append(ChatMessage(role="assistant", content=content))
    return history


def decide_mock_tool_calls(
    messages: Sequence[dict],
    options: RequestOptions,
) -> list[dict] | None:
    """Return OpenAI-style tool_calls list, or None for direct chat reply."""
    if _current_turn_has_tool_observations(messages):
        return None

    user_message = _latest_user_message(messages).strip()
    if not user_message:
        return None

    history = _history_from_messages(messages)

    if _has_any(user_message, VIDEO_KEYWORDS):
        use_session = message_references_session_image(user_message) or any(
            item.tool_result and item.tool_result.type == "image"
            for item in history
            if item.role == "assistant"
        )
        args = {
            "prompt": user_message,
            "size": coalesce_size(None, user_message, options.default_video_size),
            "duration_seconds": coalesce_duration(
                None,
                user_message,
                options.default_video_duration_seconds,
            ),
            "use_session_image": use_session,
        }
        return [_make_tool_call("generate_video", args)]

    if _has_any(user_message, IMAGE_KEYWORDS):
        args = {
            "prompt": user_message,
            "size": coalesce_size(None, user_message, options.default_image_size),
        }
        return [_make_tool_call("generate_image", args)]

    if _has_any(user_message, SEARCH_KEYWORDS):
        return [_make_tool_call("web_search", {"query": user_message})]

    return None


def mock_final_content(messages: Sequence[dict]) -> str:
    user_message = _latest_user_message(messages)
    for message in reversed(messages):
        if message.get("role") != "tool":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        if "搜索查询" in content or "摘要" in content:
            return f"根据搜索结果：{content.split('摘要：', 1)[-1].split('来源：')[0].strip()}"
        if "图片已生成" in content:
            return "已为你生成图片。"
        if "视频已生成" in content:
            return "已根据上一张图片生成视频。" if "image_to_video" in content else "已为你生成视频。"

    return f"你说的是：{user_message}"


def _make_tool_call(name: str, args: dict) -> dict:
    return {
        "id": f"call_{uuid.uuid4().hex[:12]}",
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(args, ensure_ascii=False),
        },
    }
