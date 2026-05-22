from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class IntentType(StrEnum):
    CHAT = "chat"
    SEARCH = "search"
    IMAGE = "image"
    VIDEO = "video"


PlanningMode = Literal["auto", "always", "off"]
PlanStepStatus = Literal["pending", "in_progress", "done"]
ToolResultType = Literal[
    "search",
    "fetch",
    "image",
    "video",
    "calculation",
    "code",
    "document",
    "analysis",
    "knowledge",
]


class RequestOptions(BaseModel):
    default_image_size: str = "1024x1024"
    default_video_size: str = "1280x720"
    default_video_duration_seconds: int = Field(default=5, ge=1, le=120)
    planning_mode: PlanningMode = "auto"


class AttachmentRef(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int


class TaskPlanStep(BaseModel):
    id: str
    title: str
    description: str = ""
    status: PlanStepStatus = "pending"


class TaskPlan(BaseModel):
    goal: str
    steps: list[TaskPlanStep] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


class ChatRequest(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str | None = None
    message: str = Field(min_length=1)
    options: RequestOptions = Field(default_factory=RequestOptions)
    attachments: list[str] = Field(default_factory=list)
    enable_planning: bool | None = None
    # True：仅知识库向量检索作答；False：仅联网搜索，不检索知识库
    use_knowledge_base: bool = True


class SearchResult(BaseModel):
    query: str
    summary: str
    sources: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    type: ToolResultType
    url: str | None = None
    content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_result: ToolResult | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    run_id: str | None = None
    steps: list["AgentStepSummary"] = Field(default_factory=list)
    attachments: list[AttachmentRef] = Field(default_factory=list)
    plan: TaskPlan | None = None


class AgentStepSummary(BaseModel):
    step: int
    tool_name: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict)
    observation_preview: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    intent: IntentType
    answer: str
    run_id: str = ""
    tool_result: ToolResult | None = None
    steps: list[AgentStepSummary] = Field(default_factory=list)
    plan: TaskPlan | None = None


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatMessage]


class AttachmentUploadResponse(BaseModel):
    attachments: list[AttachmentRef]
