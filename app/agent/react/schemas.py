from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolCallRequest(BaseModel):
    id: str
    name: str
    arguments: str


class LlmTurn(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)
    finish_reason: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class ToolExecutionResult(BaseModel):
    observation: str
    tool_result: Any = None  # ToolResult | None — avoid circular import at runtime


class AgentStep(BaseModel):
    step: int
    tool_name: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict)
    observation_preview: str | None = None
