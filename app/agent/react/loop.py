from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any
from uuid import uuid4

from app.agent.react.messages import (
    append_assistant_tool_calls,
    append_tool_observation,
    build_initial_messages,
    tool_calls_to_openai_dicts,
    truncate_observation,
)
from app.agent.react.schemas import AgentStep, LlmTurn, ToolCallRequest
from app.agent.planner import format_plan_for_prompt
from app.agent.schemas import (
    AgentStepSummary,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    IntentType,
    TaskPlan,
    ToolResult,
)
from app.storage.attachments import AttachmentStore
from app.agent.react.knowledge_policy import (
    knowledge_priority_system_addon,
    tool_definitions_for_run,
)
from app.agent.tools.executor import ToolExecutionContext, execute_tool_calls
from app.agent.tools.mock_routing import decide_mock_tool_calls
from app.agent.tools.registry import ToolRegistry
from app.core.logging import get_logger
from app.knowledge.retriever import KnowledgeRetriever, format_auto_retrieve_context
from app.providers.ark_client import humanize_provider_error
from app.providers.base import ChatProvider

logger = get_logger(__name__)

_STEP_LIMIT_HINT = (
    "已达最大 ReAct 步数。请根据上方 tool observation 用中文给出最终回答，"
    "不要调用任何工具。"
)


def infer_intent(tool_result: ToolResult | None) -> IntentType:
    if tool_result is None:
        return IntentType.CHAT
    if tool_result.type in {"search", "fetch"}:
        return IntentType.SEARCH
    if tool_result.type == "image":
        return IntentType.IMAGE
    if tool_result.type == "video":
        return IntentType.VIDEO
    return IntentType.CHAT


def _tool_sse_name(tool_name: str) -> str:
    mapping = {
        "web_search": "search",
        "fetch_url": "fetch",
        "generate_image": "image",
        "generate_video": "video",
        "calculator": "calc",
        "run_python": "code",
        "parse_document": "document",
        "analyze_image": "vision",
        "search_knowledge": "knowledge",
    }
    return mapping.get(tool_name, tool_name)


_MEDIA_TOOLS = frozenset({"generate_image", "generate_video"})
_SEARCH_TOOL = "web_search"
_FETCH_TOOL = "fetch_url"


def _select_tool_calls_for_step(tool_calls: list) -> tuple[list, list]:
    names = {call.name for call in tool_calls}
    if _SEARCH_TOOL in names and names.intersection(_MEDIA_TOOLS):
        execute = [call for call in tool_calls if call.name == _SEARCH_TOOL]
        deferred = [call for call in tool_calls if call.name in _MEDIA_TOOLS]
        return execute, deferred
    if _SEARCH_TOOL in names and _FETCH_TOOL in names:
        execute = [call for call in tool_calls if call.name == _SEARCH_TOOL]
        deferred = [call for call in tool_calls if call.name == _FETCH_TOOL]
        return execute, deferred
    return tool_calls, []


def _update_display_tool_result(
    current: ToolResult | None,
    new: ToolResult | None,
) -> ToolResult | None:
    if new is None:
        return current
    if new.type in {"image", "video"}:
        return new
    if current is None or current.type not in {"image", "video"}:
        return new
    return current


def _parse_tool_input(arguments: str) -> dict[str, Any]:
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _fallback_tool_calls_from_rules(
    working_messages: Sequence[dict[str, Any]],
    request: ChatRequest,
) -> list[ToolCallRequest]:
    tool_calls_raw = decide_mock_tool_calls(working_messages, request.options)
    if not tool_calls_raw:
        return []

    tool_calls: list[ToolCallRequest] = []
    for item in tool_calls_raw:
        function = item.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        arguments = function.get("arguments")
        call_id = item.get("id")
        if isinstance(name, str) and isinstance(arguments, str) and isinstance(call_id, str):
            tool_calls.append(
                ToolCallRequest(
                    id=call_id,
                    name=name,
                    arguments=arguments,
                ),
            )
    return tool_calls


def _with_run_id(run_id: str, data: dict[str, Any]) -> dict[str, Any]:
    return {**data, "run_id": run_id}


def _check_cancel(cancel_event: asyncio.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise asyncio.CancelledError()


class ReActLoop:
    def __init__(
        self,
        chat_provider: ChatProvider,
        tool_registry: ToolRegistry,
        *,
        max_steps: int = 6,
        trace_observation_max_chars: int = 4000,
        tool_timeout_seconds: int = 120,
        video_tool_timeout_seconds: int = 600,
        tool_retry_max_attempts: int = 2,
        code_exec_timeout_seconds: int = 10,
        fetch_tool_timeout_seconds: int = 60,
        attachment_store: AttachmentStore | None = None,
        knowledge_retriever: KnowledgeRetriever | None = None,
    ) -> None:
        self.chat_provider = chat_provider
        self.tool_registry = tool_registry
        self.knowledge_retriever = knowledge_retriever
        self.max_steps = max_steps
        self.trace_observation_max_chars = trace_observation_max_chars
        self.tool_timeout_seconds = tool_timeout_seconds
        self.video_tool_timeout_seconds = video_tool_timeout_seconds
        self.tool_retry_max_attempts = tool_retry_max_attempts
        self.code_exec_timeout_seconds = code_exec_timeout_seconds
        self.fetch_tool_timeout_seconds = fetch_tool_timeout_seconds
        self.attachment_store = attachment_store

    async def handle(
        self,
        request: ChatRequest,
        history: Sequence[ChatMessage],
        *,
        plan: TaskPlan | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> tuple[ChatResponse, list[ChatMessage]]:
        async for event in self._run(
            request,
            history,
            plan=plan,
            cancel_event=cancel_event,
        ):
            if event.get("event") == "final":
                data = event.get("data")
                if isinstance(data, dict):
                    trace_raw = data.pop("_trace_messages", [])
                    trace = [ChatMessage.model_validate(item) for item in trace_raw]
                    return ChatResponse.model_validate(data), trace
        fallback_run_id = str(uuid4())
        return (
            ChatResponse(
                session_id=request.session_id,
                run_id=fallback_run_id,
                intent=IntentType.CHAT,
                answer="抱歉，未能生成回答。",
            ),
            [],
        )

    async def stream_events(
        self,
        request: ChatRequest,
        history: Sequence[ChatMessage],
        *,
        plan: TaskPlan | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        async for event in self._run(
            request,
            history,
            stream_final=True,
            plan=plan,
            cancel_event=cancel_event,
        ):
            yield event

    def _persist_observation(self, observation: str) -> str:
        return truncate_observation(observation, self.trace_observation_max_chars)

    @staticmethod
    def _fallback_answer_from_working_messages(
        working_messages: list[dict[str, Any]],
    ) -> str | None:
        search_blocks: list[str] = []
        fetch_blocks: list[str] = []
        has_image_result = False
        has_video_result = False
        for message in working_messages:
            if message.get("role") != "tool":
                continue
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            if "搜索查询" in content or "摘要：" in content:
                search_blocks.append(content.strip())
            elif "正文：" in content or content.startswith("["):
                fetch_blocks.append(content.strip())
            elif "图片已生成" in content:
                has_image_result = True
            elif "视频已生成" in content:
                has_video_result = True

        if has_video_result:
            return "已为你生成视频。"
        if has_image_result:
            return "已为你生成图片。"
        if not search_blocks and not fetch_blocks:
            return None

        parts = [
            "根据本轮已完成的工具结果，整理如下（大模型最终汇总暂时不可用，内容来自搜索/抓取工具）：",
            "",
        ]
        if search_blocks:
            parts.append("## 联网搜索")
            parts.append(search_blocks[-1][:4000])
        if fetch_blocks:
            parts.append("")
            parts.append("## 网页阅读")
            parts.append(fetch_blocks[-1][:4000])
        parts.append("")
        parts.append(
            "说明：部分链接可能 404 或无法连接；请以上述**搜索摘要**为主作答，"
            "并注明未能读取全文的链接。"
        )
        return "\n".join(parts)

    async def _answer_text_from_messages(
        self,
        working_messages: list[dict[str, Any]],
    ) -> str:
        try:
            answer = ""
            async for chunk in self.chat_provider.stream_working_messages(working_messages):
                answer += chunk
            answer = answer.strip()
            if answer:
                return answer
        except Exception as exc:
            logger.warning(
                "stream_final_failed",
                extra={"event": "stream_final_failed", "error": str(exc) or type(exc).__name__},
            )
            complete_fn = getattr(self.chat_provider, "complete_working_messages", None)
            if complete_fn is not None:
                try:
                    text = (await complete_fn(working_messages)).strip()
                    if text:
                        return text
                except Exception as complete_exc:
                    logger.warning(
                        "complete_final_failed",
                        extra={
                            "event": "complete_final_failed",
                            "error": str(complete_exc) or type(complete_exc).__name__,
                        },
                    )

        fallback = self._fallback_answer_from_working_messages(working_messages)
        if fallback:
            return fallback
        raise RuntimeError("无法生成最终回答")

    def _record_assistant_tool_calls(
        self,
        run_trace: list[ChatMessage],
        *,
        run_id: str,
        turn_content: str | None,
        tool_calls: Sequence[ToolCallRequest],
    ) -> None:
        run_trace.append(
            ChatMessage(
                role="assistant",
                content=turn_content or "",
                tool_calls=tool_calls_to_openai_dicts(tool_calls),
                run_id=run_id,
            ),
        )

    def _record_tool_observation(
        self,
        run_trace: list[ChatMessage],
        *,
        run_id: str,
        tool_call_id: str,
        observation: str,
    ) -> str:
        persisted = self._persist_observation(observation)
        run_trace.append(
            ChatMessage(
                role="tool",
                content=persisted,
                tool_call_id=tool_call_id,
                run_id=run_id,
            ),
        )
        return persisted

    async def _produce_answer_deltas(
        self,
        working_messages: list[dict[str, Any]],
        *,
        run_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        async for chunk in self.chat_provider.stream_working_messages(working_messages):
            yield {
                "event": "delta",
                "data": _with_run_id(run_id, {"text": chunk}),
            }

    async def _stream_final_answer(
        self,
        working_messages: list[dict[str, Any]],
        *,
        run_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        try:
            async for delta_event in self._produce_answer_deltas(
                working_messages,
                run_id=run_id,
            ):
                yield delta_event
        except Exception as exc:
            logger.warning(
                "stream_final_failed",
                extra={"event": "stream_final_failed", "error": str(exc) or type(exc).__name__},
            )
            text = await self._answer_text_from_messages(working_messages)
            chunk_size = 16
            for index in range(0, len(text), chunk_size):
                yield {
                    "event": "delta",
                    "data": _with_run_id(run_id, {"text": text[index : index + chunk_size]}),
                }

    async def _run(
        self,
        request: ChatRequest,
        history: Sequence[ChatMessage],
        *,
        stream_final: bool = False,
        plan: TaskPlan | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        run_id = str(uuid4())
        plan_prompt = format_plan_for_prompt(plan) if plan else None
        settings = self.tool_registry.settings
        knowledge_context: str | None = None
        auto_retrieve_tool_result: ToolResult | None = None
        user_id = request.user_id or ""
        use_knowledge_base = (
            request.use_knowledge_base
            and settings.knowledge_enabled
            and self.knowledge_retriever is not None
        )

        if (
            use_knowledge_base
            and settings.knowledge_auto_retrieve
            and user_id
        ):
            try:
                search = await self.knowledge_retriever.search(
                    user_id,
                    request.message,
                )
                if search.citations:
                    knowledge_context = format_auto_retrieve_context(
                        search.citations,
                    )
                    auto_retrieve_tool_result = ToolResult(
                        type="knowledge",
                        content=search.summary,
                        metadata={
                            "query": search.query,
                            "citations": [c.model_dump() for c in search.citations],
                            "auto_retrieve": True,
                        },
                    )
            except Exception as exc:
                logger.warning(
                    "knowledge_auto_retrieve_failed",
                    extra={"error": str(exc)},
                )

        knowledge_priority_addon = knowledge_priority_system_addon(
            use_knowledge_base=use_knowledge_base,
        )
        tool_definitions = tool_definitions_for_run(
            use_knowledge_base=use_knowledge_base,
        )

        working_messages = build_initial_messages(
            history,
            request.message,
            plan_prompt=plan_prompt,
            knowledge_context=knowledge_context,
            knowledge_priority_addon=knowledge_priority_addon or None,
            attachment_ids=request.attachments,
            attachment_store=self.attachment_store,
            user_id=user_id,
            session_id=request.session_id,
            multimodal_inline=settings.multimodal_inline_attachments,
            multimodal_inline_max_bytes=settings.multimodal_inline_max_bytes,
            settings=settings,
        )
        run_trace: list[ChatMessage] = []
        if plan is not None:
            run_trace.append(
                ChatMessage(
                    role="assistant",
                    content="已生成任务计划，开始执行。",
                    plan=plan,
                    run_id=run_id,
                ),
            )
        last_tool_result: ToolResult | None = auto_retrieve_tool_result
        display_tool_result: ToolResult | None = auto_retrieve_tool_result
        steps: list[AgentStep] = []
        answer = ""
        hit_step_limit = False
        tool_context = ToolExecutionContext(
            user_id=request.user_id or "",
            session_id=request.session_id,
            user_message=request.message,
            history=history,
            options=request.options,
            use_knowledge_base=use_knowledge_base,
        )

        yield {
            "event": "run_started",
            "data": _with_run_id(run_id, {"max_steps": self.max_steps}),
        }

        try:
            for step_index in range(1, self.max_steps + 1):
                _check_cancel(cancel_event)

                yield {
                    "event": "step_started",
                    "data": _with_run_id(
                        run_id,
                        {"step": step_index, "max_steps": self.max_steps},
                    ),
                }

                try:
                    turn = await self.chat_provider.complete_with_tools(
                        working_messages,
                        tool_definitions,
                    )
                except Exception as exc:
                    fallback_tool_calls = _fallback_tool_calls_from_rules(
                        working_messages,
                        request,
                    )
                    if not fallback_tool_calls:
                        raise
                    logger.warning(
                        "llm_tool_routing_failed_using_rule_fallback",
                        extra={
                            "event": "llm_tool_routing_failed_using_rule_fallback",
                            "error": str(exc) or type(exc).__name__,
                            "tool_names": [call.name for call in fallback_tool_calls],
                        },
                    )
                    turn = LlmTurn(
                        tool_calls=fallback_tool_calls,
                        finish_reason="tool_calls",
                    )

                if turn.has_tool_calls:
                    append_assistant_tool_calls(
                        working_messages,
                        turn.content,
                        turn.tool_calls,
                    )
                    self._record_assistant_tool_calls(
                        run_trace,
                        run_id=run_id,
                        turn_content=turn.content,
                        tool_calls=turn.tool_calls,
                    )

                    calls_to_run, deferred_calls = _select_tool_calls_for_step(
                        turn.tool_calls,
                    )

                    for call in calls_to_run:
                        tool_input = _parse_tool_input(call.arguments)
                        sse_tool = _tool_sse_name(call.name)
                        yield {
                            "event": "tool_started",
                            "data": _with_run_id(
                                run_id,
                                {
                                    "step": step_index,
                                    "tool": sse_tool,
                                    "input": tool_input,
                                },
                            ),
                        }

                    _check_cancel(cancel_event)
                    started = time.perf_counter()
                    outcomes = await execute_tool_calls(
                        self.tool_registry,
                        calls_to_run,
                        context=tool_context,
                        tool_timeout_seconds=float(self.tool_timeout_seconds),
                        video_tool_timeout_seconds=float(self.video_tool_timeout_seconds),
                        code_exec_timeout_seconds=float(self.code_exec_timeout_seconds),
                        fetch_tool_timeout_seconds=float(self.fetch_tool_timeout_seconds),
                        max_attempts=self.tool_retry_max_attempts,
                    )
                    logger.info(
                        "tools_executed",
                        extra={
                            "run_id": run_id,
                            "session_id": request.session_id,
                            "event": "tools_executed",
                            "latency_ms": int((time.perf_counter() - started) * 1000),
                            "step": step_index,
                        },
                    )

                    for outcome in outcomes:
                        call = outcome.call
                        execution = outcome.execution
                        tool_input = _parse_tool_input(call.arguments)

                        if outcome.error_message:
                            yield {
                                "event": "error",
                                "data": _with_run_id(
                                    run_id,
                                    {"message": outcome.error_message},
                                ),
                            }

                        persisted = self._record_tool_observation(
                            run_trace,
                            run_id=run_id,
                            tool_call_id=call.id,
                            observation=execution.observation,
                        )
                        append_tool_observation(
                            working_messages,
                            tool_call_id=call.id,
                            observation=persisted,
                        )

                        if execution.tool_result is not None:
                            last_tool_result = execution.tool_result
                            display_tool_result = _update_display_tool_result(
                                display_tool_result,
                                execution.tool_result,
                            )
                            yield {
                                "event": "tool_result",
                                "data": _with_run_id(
                                    run_id,
                                    last_tool_result.model_dump(mode="json"),
                                ),
                            }

                        steps.append(
                            AgentStep(
                                step=step_index,
                                tool_name=call.name,
                                tool_input=tool_input,
                                observation_preview=execution.observation[:200],
                            ),
                        )

                    for call in deferred_calls:
                        if call.name == _FETCH_TOOL:
                            skip_observation = (
                                "已跳过与本步并行调用的 fetch_url 请求。"
                                "请先阅读上方 web_search 的 observation 中的来源链接，"
                                "在下一轮仅调用 fetch_url，传入最相关的 1–3 个 URL。"
                            )
                        else:
                            skip_observation = (
                                "已跳过与本步并行调用的生图/生视频请求。"
                                "请先阅读上方 web_search 的 observation，"
                                "在下一轮仅调用 generate_image 或 generate_video，"
                                "且 prompt 须结合搜索摘要与用户需求。"
                            )
                        persisted = self._record_tool_observation(
                            run_trace,
                            run_id=run_id,
                            tool_call_id=call.id,
                            observation=skip_observation,
                        )
                        append_tool_observation(
                            working_messages,
                            tool_call_id=call.id,
                            observation=persisted,
                        )

                    continue

                if turn.content and turn.content.strip():
                    if stream_final:
                        answer = ""
                        async for delta_event in self._stream_final_answer(
                            working_messages,
                            run_id=run_id,
                        ):
                            yield delta_event
                            answer += str(delta_event["data"].get("text") or "")
                        answer = answer.strip()
                        if not answer:
                            answer = turn.content.strip()
                    else:
                        answer = turn.content.strip()
                    break

            if not answer:
                hit_step_limit = True
                yield {
                    "event": "step_limit",
                    "data": _with_run_id(
                        run_id,
                        {"max_steps": self.max_steps},
                    ),
                }
                working_messages.append({"role": "user", "content": _STEP_LIMIT_HINT})
                _check_cancel(cancel_event)
                if stream_final:
                    answer = ""
                    async for delta_event in self._stream_final_answer(
                        working_messages,
                        run_id=run_id,
                    ):
                        yield delta_event
                        answer += str(delta_event["data"].get("text") or "")
                    answer = answer.strip()
                else:
                    answer = await self._answer_text_from_messages(working_messages)

            if not answer and not hit_step_limit:
                _check_cancel(cancel_event)
                if stream_final:
                    answer = ""
                    async for delta_event in self._stream_final_answer(
                        working_messages,
                        run_id=run_id,
                    ):
                        yield delta_event
                        answer += str(delta_event["data"].get("text") or "")
                    answer = answer.strip()
                else:
                    answer = await self._answer_text_from_messages(working_messages)

        except asyncio.CancelledError:
            logger.info(
                "run_cancelled",
                extra={
                    "run_id": run_id,
                    "session_id": request.session_id,
                    "event": "run_cancelled",
                },
            )
            raise
        except Exception as exc:
            fallback = self._fallback_answer_from_working_messages(working_messages)
            if fallback:
                answer = fallback
                yield {
                    "event": "error",
                    "data": _with_run_id(
                        run_id,
                        {"message": "最终汇总调用大模型失败，已根据工具结果生成备用回答。"},
                    ),
                }
                if stream_final:
                    chunk_size = 16
                    for index in range(0, len(answer), chunk_size):
                        yield {
                            "event": "delta",
                            "data": _with_run_id(
                                run_id,
                                {"text": answer[index : index + chunk_size]},
                            ),
                        }
            else:
                answer = f"抱歉，{humanize_provider_error(exc)}"
                yield {
                    "event": "error",
                    "data": _with_run_id(run_id, {"message": humanize_provider_error(exc)}),
                }
                if stream_final and answer:
                    yield {
                        "event": "delta",
                        "data": _with_run_id(run_id, {"text": answer}),
                    }

        step_summaries = [
            AgentStepSummary(
                step=step.step,
                tool_name=step.tool_name,
                tool_input=step.tool_input,
                observation_preview=step.observation_preview,
            )
            for step in steps
        ]
        persisted_tool_result = display_tool_result if display_tool_result else last_tool_result
        final_assistant = ChatMessage(
            role="assistant",
            content=answer,
            tool_result=persisted_tool_result,
            run_id=run_id,
            steps=step_summaries,
        )
        run_trace.append(final_assistant)

        response = ChatResponse(
            session_id=request.session_id,
            run_id=run_id,
            intent=infer_intent(persisted_tool_result),
            answer=answer,
            tool_result=persisted_tool_result,
            steps=step_summaries,
            plan=plan,
        )
        final_data = response.model_dump(mode="json")
        final_data["_trace_messages"] = [
            message.model_dump(mode="json") for message in run_trace
        ]
        yield {
            "event": "final",
            "data": _with_run_id(run_id, final_data),
        }
