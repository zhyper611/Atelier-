from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.agent.react.prompts import build_react_system_prompt
from app.core.config import Settings
from app.agent.react.schemas import ToolCallRequest
from app.agent.schemas import ChatMessage, TaskPlan
from app.agent.tools.media_parts import attachment_to_content_part, build_data_url
from app.storage.attachments import AttachmentStore


def truncate_observation(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def history_item_to_working_message(item: ChatMessage) -> dict[str, Any] | None:
    if item.role == "user":
        return {"role": "user", "content": item.content}
    if item.role == "system":
        return {"role": "system", "content": item.content}
    if item.role == "tool":
        if not item.tool_call_id:
            return None
        return {
            "role": "tool",
            "tool_call_id": item.tool_call_id,
            "content": item.content,
        }
    if item.role == "assistant":
        if item.tool_calls:
            payload: dict[str, Any] = {
                "role": "assistant",
                "content": item.content or None,
                "tool_calls": item.tool_calls,
            }
            return payload
        return {"role": "assistant", "content": item.content}
    return None


def _classify_attachment_mime(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("audio/"):
        return "audio"
    return "document"


def _build_user_content(
    user_message: str,
    attachment_ids: list[str],
    attachment_store: AttachmentStore | None,
    user_id: str,
    session_id: str,
    *,
    multimodal_inline: bool = False,
    multimodal_inline_max_bytes: int = 4_194_304,
) -> str | list[dict[str, Any]]:
    if not attachment_ids or attachment_store is None:
        return user_message

    image_ids: list[str] = []
    video_ids: list[str] = []
    audio_ids: list[str] = []
    document_ids: list[str] = []
    media_parts: list[dict[str, Any]] = []

    for attachment_id in attachment_ids:
        try:
            ref, data = attachment_store.read_bytes(user_id, session_id, attachment_id)
        except Exception:
            document_ids.append(attachment_id)
            continue

        kind = _classify_attachment_mime(ref.mime_type)
        if kind == "image":
            image_ids.append(attachment_id)
        elif kind == "video":
            video_ids.append(attachment_id)
        elif kind == "audio":
            audio_ids.append(attachment_id)
        else:
            document_ids.append(attachment_id)

        if multimodal_inline and len(data) <= multimodal_inline_max_bytes and kind in {
            "image",
            "video",
            "audio",
        }:
            try:
                data_url = build_data_url(ref.mime_type, data)
                media_parts.append(attachment_to_content_part(ref.mime_type, data_url))
            except ValueError:
                pass

    hint_parts = [user_message]
    if image_ids:
        hint_parts.append(
            "\n\n[图片附件] attachment_id："
            + ", ".join(image_ids)
            + "。可直接理解内联画面；若需更细分析可调用 analyze_image(attachment_id, question)。"
        )
    if video_ids:
        hint_parts.append(
            "\n\n[视频附件] attachment_id："
            + ", ".join(video_ids)
            + "。已尝试内联视频内容，请结合画面与声音理解。"
        )
    if audio_ids:
        hint_parts.append(
            "\n\n[音频附件] attachment_id："
            + ", ".join(audio_ids)
            + "。已尝试内联音频，请转写或总结要点。"
        )
    if document_ids:
        hint_parts.append(
            "\n\n[文档附件] attachment_id："
            + ", ".join(document_ids)
            + "。需要正文请调用 parse_document(attachment_id)。"
        )

    text = "\n".join(hint_parts)
    if not media_parts:
        return text

    return [{"type": "text", "text": text}, *media_parts]


def normalize_messages_for_api(messages: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge all system messages into one at index 0 (required by many gateways)."""
    system_parts: list[str] = []
    rest: list[dict[str, Any]] = []

    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "system" and isinstance(content, str) and content.strip():
            system_parts.append(content.strip())
            continue
        rest.append(dict(message))

    if not system_parts:
        return list(messages)

    merged_system = {"role": "system", "content": "\n\n".join(system_parts)}
    return [merged_system, *rest]


def collapse_messages_for_streaming_completion(
    messages: Sequence[dict[str, Any]],
    *,
    max_tool_context_chars: int = 12_000,
) -> list[dict[str, Any]]:
    """Fold tool-call trace into plain messages for the final streaming LLM call.

    Some gateways (e.g. Volc Ark) reject ``role: tool`` or assistant messages that
    only contain ``tool_calls`` when the request does not include a ``tools`` field.
    """
    has_tool_trace = any(message.get("role") == "tool" for message in messages)
    if not has_tool_trace:
        return normalize_messages_for_api(messages)

    system_parts: list[str] = []
    prefix: list[dict[str, Any]] = []
    tool_blocks: list[str] = []
    in_tool_trace = False

    for message in messages:
        role = message.get("role")
        if role == "system":
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                system_parts.append(content.strip())
            continue

        if role == "tool":
            in_tool_trace = True
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                tool_blocks.append(content.strip())
            continue

        if role == "assistant" and message.get("tool_calls"):
            in_tool_trace = True
            continue

        if role in {"user", "assistant"}:
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                entry = {"role": role, "content": content.strip()}
                if not in_tool_trace:
                    prefix.append(entry)
                else:
                    prefix.append(entry)
            elif isinstance(content, list) and not in_tool_trace:
                prefix.append(dict(message))

    collapsed: list[dict[str, Any]] = []
    if system_parts:
        collapsed.append({"role": "system", "content": "\n\n".join(system_parts)})
    collapsed.extend(prefix)

    if tool_blocks:
        combined_tools = "\n\n---\n\n".join(tool_blocks)
        if len(combined_tools) > max_tool_context_chars:
            combined_tools = (
                combined_tools[: max_tool_context_chars - 20]
                + "\n…（工具结果已截断）"
            )
        collapsed.append(
            {
                "role": "user",
                "content": (
                    "【以下为工具执行结果，请据此回答用户问题；"
                    "不要编造未出现的信息；若某链接失败请说明并换用搜索摘要】\n\n"
                    + combined_tools
                ),
            },
        )

    if not collapsed:
        return normalize_messages_for_api(messages)
    return normalize_messages_for_api(collapsed)


def build_initial_messages(
    history: Sequence[ChatMessage],
    user_message: str,
    *,
    plan: TaskPlan | None = None,
    plan_prompt: str | None = None,
    knowledge_context: str | None = None,
    knowledge_priority_addon: str | None = None,
    attachment_ids: list[str] | None = None,
    attachment_store: AttachmentStore | None = None,
    user_id: str = "",
    session_id: str = "",
    multimodal_inline: bool = False,
    multimodal_inline_max_bytes: int = 4_194_304,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    del plan
    system_content = build_react_system_prompt(settings)
    if plan_prompt:
        system_content = f"{system_content}\n\n{plan_prompt}"
    if knowledge_priority_addon:
        system_content = f"{system_content}\n\n{knowledge_priority_addon}"
    if knowledge_context:
        system_content = f"{system_content}\n\n{knowledge_context}"

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_content},
    ]

    for item in history:
        converted = history_item_to_working_message(item)
        if converted is not None:
            messages.append(converted)

    user_content = _build_user_content(
        user_message,
        attachment_ids or [],
        attachment_store,
        user_id,
        session_id,
        multimodal_inline=multimodal_inline,
        multimodal_inline_max_bytes=multimodal_inline_max_bytes,
    )
    messages.append({"role": "user", "content": user_content})
    return normalize_messages_for_api(messages)


def tool_calls_to_openai_dicts(tool_calls: Sequence[ToolCallRequest]) -> list[dict[str, Any]]:
    return [
        {
            "id": call.id,
            "type": "function",
            "function": {
                "name": call.name,
                "arguments": call.arguments,
            },
        }
        for call in tool_calls
    ]


def append_assistant_tool_calls(
    messages: list[dict[str, Any]],
    turn_content: str | None,
    tool_calls: Sequence[ToolCallRequest],
) -> None:
    payload: dict[str, Any] = {
        "role": "assistant",
        "content": turn_content,
        "tool_calls": tool_calls_to_openai_dicts(tool_calls),
    }
    messages.append(payload)


def append_tool_observation(
    messages: list[dict[str, Any]],
    *,
    tool_call_id: str,
    observation: str,
) -> None:
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": observation,
        },
    )


def working_messages_to_chat_messages(messages: list[dict[str, Any]]) -> list[ChatMessage]:
    """Convert working trace to ChatMessage list for complete() fallback."""
    result: list[ChatMessage] = []
    for message in messages:
        role = message.get("role")
        if role not in {"user", "assistant", "system"}:
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            result.append(ChatMessage(role=role, content=content))
        elif isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            combined = " ".join(str(t) for t in text_parts if t).strip()
            if combined:
                result.append(ChatMessage(role=role, content=combined))
    return result
