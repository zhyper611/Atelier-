from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from app.agent.react.schemas import ToolExecutionResult
from app.agent.schemas import ChatMessage, RequestOptions, ToolResult
from app.agent.session_context import message_references_session_image, resolve_video_reference_image
from app.agent.tools.calculator import safe_evaluate
from app.agent.tools.document_parser import parse_attachment_text
from app.agent.tools.params import coalesce_duration, coalesce_size
from app.agent.tools.url_fetcher import (
    UrlFetchError,
    coerce_urls,
    fetch_urls,
    format_fetch_observation,
    results_to_metadata,
)
from app.agent.tools.vision import analyze_session_image
from app.core.config import Settings
from app.knowledge.retriever import format_citations_observation
from app.knowledge.store import KnowledgeStore
from app.providers.base import ChatProvider, ImageProvider, SearchProvider, VideoProvider
from app.storage.attachments import AttachmentStore


class ToolRegistry:
    def __init__(
        self,
        search_provider: SearchProvider,
        image_provider: ImageProvider,
        video_provider: VideoProvider,
        chat_provider: ChatProvider,
        attachment_store: AttachmentStore,
        settings: Settings,
        knowledge_store: KnowledgeStore | None = None,
    ) -> None:
        self.search_provider = search_provider
        self.image_provider = image_provider
        self.video_provider = video_provider
        self.chat_provider = chat_provider
        self.attachment_store = attachment_store
        self.settings = settings
        self.knowledge_store = knowledge_store

    async def execute(
        self,
        name: str,
        arguments: str,
        *,
        user_id: str,
        session_id: str,
        user_message: str,
        history: Sequence[ChatMessage],
        options: RequestOptions,
        use_knowledge_base: bool = True,
    ) -> ToolExecutionResult:
        args = _parse_arguments(arguments)

        if use_knowledge_base and name in {"web_search", "fetch_url"}:
            return ToolExecutionResult(
                observation=(
                    "当前为知识库检索模式，禁止联网。请仅依据已注入的知识库片段作答，"
                    "或调用 search_knowledge；证据不足时必须说明"
                    "「我在当前知识库中没有找到足够信息回答这个问题。」，不得编造。"
                ),
            )
        if not use_knowledge_base and name == "search_knowledge":
            return ToolExecutionResult(
                observation=(
                    "当前为联网检索模式，禁止检索知识库。请使用 web_search 获取外部信息。"
                ),
            )

        if name == "web_search":
            query = str(args.get("query") or user_message).strip()
            search_result = await self.search_provider.search(query)
            tool_result = ToolResult(
                type="search",
                content=search_result.summary,
                metadata={"sources": search_result.sources, "query": search_result.query},
            )
            sources = "\n".join(search_result.sources) if search_result.sources else "无"
            observation = (
                f"搜索查询：{search_result.query}\n"
                f"摘要：{search_result.summary}\n"
                f"来源：{sources}"
            )
            return ToolExecutionResult(observation=observation, tool_result=tool_result)

        if name == "fetch_url":
            if not self.settings.fetch_url_enabled:
                return ToolExecutionResult(observation="网页抓取功能已关闭。")
            urls = coerce_urls(args.get("urls"), args.get("url"))
            if not urls:
                return ToolExecutionResult(
                    observation="fetch_url 缺少 urls 参数，请提供至少一个 http(s) 链接。",
                )
            try:
                results = await fetch_urls(urls, self.settings)
            except UrlFetchError as exc:
                return ToolExecutionResult(observation=f"网页抓取失败：{exc}")
            observation = format_fetch_observation(results)
            merged_text = "\n\n".join(
                r.text for r in results if r.text and not r.error
            ) or observation
            tool_result = ToolResult(
                type="fetch",
                content=merged_text[: self.settings.fetch_url_max_content_chars],
                metadata=results_to_metadata(results),
            )
            return ToolExecutionResult(observation=observation, tool_result=tool_result)

        if name == "calculator":
            expression = str(args.get("expression") or "").strip()
            if not expression:
                return ToolExecutionResult(observation="calculator 缺少 expression 参数。")
            try:
                result = safe_evaluate(expression)
            except ValueError as exc:
                return ToolExecutionResult(observation=f"计算失败：{exc}")
            tool_result = ToolResult(
                type="calculation",
                content=str(result),
                metadata={"expression": expression, "result": result},
            )
            return ToolExecutionResult(
                observation=f"计算结果：{expression} = {result}",
                tool_result=tool_result,
            )

        if name == "search_knowledge":
            if self.knowledge_store is None or not self.knowledge_store.enabled:
                return ToolExecutionResult(
                    observation="知识库未启用或 Redis Stack 不可用，无法检索。",
                )
            query = str(args.get("query") or user_message).strip()
            if not query:
                return ToolExecutionResult(observation="search_knowledge 缺少 query 参数。")
            top_k = args.get("top_k")
            k = int(top_k) if top_k is not None else self.settings.knowledge_top_k
            k = max(1, min(k, 20))
            try:
                citations = await self.knowledge_store.search(user_id, query, top_k=k)
            except Exception as exc:
                return ToolExecutionResult(observation=f"知识库检索失败：{exc}")
            observation = format_citations_observation(citations)
            citations_payload = [c.model_dump() for c in citations]
            summary = "\n".join(
                f"[{c['index']}] {c['filename']}: {c['excerpt'][:200]}"
                for c in citations_payload
            )
            tool_result = ToolResult(
                type="knowledge",
                content=summary or observation,
                metadata={"query": query, "citations": citations_payload},
            )
            return ToolExecutionResult(observation=observation, tool_result=tool_result)

        if name == "parse_document":
            attachment_id = str(args.get("attachment_id") or "").strip()
            if not attachment_id:
                return ToolExecutionResult(observation="parse_document 缺少 attachment_id。")
            try:
                filename, text = parse_attachment_text(
                    self.attachment_store,
                    user_id,
                    session_id,
                    attachment_id,
                )
            except Exception as exc:
                return ToolExecutionResult(observation=f"文档解析失败：{exc}")
            tool_result = ToolResult(
                type="document",
                content=text,
                metadata={"filename": filename, "attachment_id": attachment_id},
            )
            preview = text[:500] + ("..." if len(text) > 500 else "")
            return ToolExecutionResult(
                observation=f"已解析文档「{filename}」。正文预览：\n{preview}",
                tool_result=tool_result,
            )

        if name == "analyze_image":
            attachment_id = str(args.get("attachment_id") or "").strip()
            question = str(args.get("question") or "").strip() or None
            if not attachment_id:
                return ToolExecutionResult(observation="analyze_image 缺少 attachment_id。")
            try:
                filename, description = await analyze_session_image(
                    self.chat_provider,
                    self.attachment_store,
                    user_id,
                    session_id,
                    attachment_id,
                    question,
                )
            except Exception as exc:
                return ToolExecutionResult(
                    observation=(
                        f"识图失败：{exc}。"
                        "若模型不支持多模态，请让用户用文字描述图片。"
                    ),
                )
            tool_result = ToolResult(
                type="analysis",
                content=description,
                metadata={"filename": filename, "attachment_id": attachment_id},
            )
            return ToolExecutionResult(
                observation=(
                    f"图片「{filename}」分析结果：\n{description}\n"
                    "请将以上分析整理后直接回复用户，不要描述工具调用过程或步骤清单。"
                ),
                tool_result=tool_result,
            )

        if name == "generate_image":
            prompt = str(args.get("prompt") or "").strip()
            if not prompt:
                return ToolExecutionResult(
                    observation=(
                        "generate_image 缺少 prompt 参数。"
                        "请根据搜索摘要与用户需求，填写具体海报画面描述后再调用。"
                    ),
                )
            size = coalesce_size(
                args.get("size"),
                f"{prompt} {user_message}",
                options.default_image_size,
            )
            tool_result = await self.image_provider.generate(prompt, size)
            observation = f"图片已生成。尺寸：{size}。请向用户确认并提供简要说明。"
            return ToolExecutionResult(observation=observation, tool_result=tool_result)

        if name == "generate_video":
            prompt = str(args.get("prompt") or user_message).strip()
            size = coalesce_size(
                args.get("size"),
                f"{prompt} {user_message}",
                options.default_video_size,
            )
            duration_seconds = coalesce_duration(
                args.get("duration_seconds"),
                f"{prompt} {user_message}",
                options.default_video_duration_seconds,
            )
            use_session_image = bool(args.get("use_session_image", False))
            if not use_session_image and message_references_session_image(user_message):
                use_session_image = True

            reference_image = resolve_video_reference_image(
                user_message,
                history,
                use_session_image=use_session_image,
            )
            reference_image_url = reference_image.url if reference_image else None
            tool_result = await self.video_provider.generate(
                prompt,
                size,
                duration_seconds,
                reference_image_url=reference_image_url,
            )
            mode = "image_to_video" if reference_image_url else "text_to_video"
            observation = (
                f"视频已生成。模式：{mode}，时长 {duration_seconds} 秒，尺寸 {size}。"
                "请向用户确认。"
            )
            return ToolExecutionResult(observation=observation, tool_result=tool_result)

        raise ValueError(f"Unknown tool: {name}")


def _parse_arguments(arguments: str) -> dict[str, Any]:
    if not arguments or not arguments.strip():
        return {}
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid tool arguments JSON: {arguments}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"Tool arguments must be an object: {arguments}")
    return parsed
