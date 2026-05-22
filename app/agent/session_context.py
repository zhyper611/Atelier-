from __future__ import annotations

import re
from collections.abc import Sequence

from app.agent.schemas import ChatMessage, ToolResult

IMAGE_REFERENCE_KEYWORDS = (
    "刚才",
    "刚刚",
    "上一张",
    "这张图",
    "这张图片",
    "上述图片",
    "刚生成",
    "刚才生成",
    "刚画",
    "基于图",
    "根据图",
    "用这张",
    "用这个图",
    "把它",
    "让它动",
    "让它",
    "动一下",
    "做成视频",
    "变成视频",
)

IMAGE_REFERENCE_PATTERNS = (
    re.compile(r"根据.{0,12}图"),
    re.compile(r"基于.{0,12}图"),
    re.compile(r"用.{0,8}图.{0,6}生成"),
)


def message_references_session_image(message: str) -> bool:
    normalized = message.strip()
    if not normalized:
        return False
    if any(keyword in normalized for keyword in IMAGE_REFERENCE_KEYWORDS):
        return True
    return any(pattern.search(normalized) for pattern in IMAGE_REFERENCE_PATTERNS)


def find_latest_session_image(history: Sequence[ChatMessage]) -> ToolResult | None:
    for message in reversed(history):
        if message.role != "assistant":
            continue
        tool_result = message.tool_result
        if tool_result is None or tool_result.type != "image":
            continue
        if tool_result.url and tool_result.url.strip():
            return tool_result
    return None


def resolve_video_reference_image(
    message: str,
    history: Sequence[ChatMessage],
    *,
    use_session_image: bool = False,
) -> ToolResult | None:
    if not use_session_image and not message_references_session_image(message):
        return None
    return find_latest_session_image(history)
