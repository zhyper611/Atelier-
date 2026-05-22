from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from app.agent.react.schemas import ToolCallRequest, ToolExecutionResult
from app.agent.schemas import ChatMessage, RequestOptions
from app.agent.tools.registry import ToolRegistry
from app.providers.ark_client import ArkApiError, humanize_provider_error


@dataclass(frozen=True)
class ToolExecutionContext:
    user_id: str
    session_id: str
    user_message: str
    history: Sequence[ChatMessage]
    options: RequestOptions
    use_knowledge_base: bool = True


def _is_retriable(exc: BaseException) -> bool:
    if isinstance(exc, asyncio.TimeoutError):
        return True
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, ArkApiError):
        status = exc.status_code
        return status is None or status >= 500
    return False


def _timeout_for_tool(
    name: str,
    default_timeout: float,
    video_timeout: float,
    code_timeout: float,
    fetch_timeout: float,
) -> float:
    if name == "generate_video":
        return video_timeout
    if name == "run_python":
        return code_timeout
    if name == "fetch_url":
        return fetch_timeout
    return default_timeout


async def _execute_one(
    registry: ToolRegistry,
    call: ToolCallRequest,
    *,
    context: ToolExecutionContext,
    timeout: float,
    max_attempts: int,
) -> ToolExecutionResult:
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return await asyncio.wait_for(
                registry.execute(
                    call.name,
                    call.arguments,
                    user_id=context.user_id,
                    session_id=context.session_id,
                    user_message=context.user_message,
                    history=context.history,
                    options=context.options,
                    use_knowledge_base=context.use_knowledge_base,
                ),
                timeout=timeout,
            )
        except Exception as exc:
            last_exc = exc
            if attempt + 1 >= max_attempts or not _is_retriable(exc):
                observation = f"工具执行失败：{humanize_provider_error(exc)}"
                return ToolExecutionResult(observation=observation)
            await asyncio.sleep(0.5 * (2**attempt))
    if last_exc is not None:
        return ToolExecutionResult(
            observation=f"工具执行失败：{humanize_provider_error(last_exc)}",
        )
    return ToolExecutionResult(observation="工具执行失败：未知错误")


@dataclass
class ToolCallOutcome:
    call: ToolCallRequest
    execution: ToolExecutionResult
    error_message: str | None = None


async def execute_tool_calls(
    registry: ToolRegistry,
    calls: Sequence[ToolCallRequest],
    *,
    context: ToolExecutionContext,
    tool_timeout_seconds: float = 120.0,
    video_tool_timeout_seconds: float = 600.0,
    code_exec_timeout_seconds: float = 10.0,
    fetch_tool_timeout_seconds: float = 60.0,
    max_attempts: int = 2,
) -> list[ToolCallOutcome]:
    if not calls:
        return []

    async def run_call(call: ToolCallRequest) -> ToolCallOutcome:
        timeout = _timeout_for_tool(
            call.name,
            tool_timeout_seconds,
            video_tool_timeout_seconds,
            code_exec_timeout_seconds,
            fetch_tool_timeout_seconds,
        )
        try:
            execution = await _execute_one(
                registry,
                call,
                context=context,
                timeout=timeout,
                max_attempts=max_attempts,
            )
            error_message = None
            if execution.observation.startswith("工具执行失败"):
                error_message = execution.observation
            return ToolCallOutcome(call=call, execution=execution, error_message=error_message)
        except Exception as exc:
            observation = f"工具执行失败：{humanize_provider_error(exc)}"
            return ToolCallOutcome(
                call=call,
                execution=ToolExecutionResult(observation=observation),
                error_message=humanize_provider_error(exc),
            )

    results = await asyncio.gather(*(run_call(call) for call in calls))
    return list(results)
