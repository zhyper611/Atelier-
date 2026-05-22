from __future__ import annotations

from app.agent.schemas import ChatMessage, ChatRequest, RequestOptions, TaskPlan, TaskPlanStep
from app.core.config import Settings
from app.providers.base import ChatProvider

_PLAN_KEYWORDS = (
    "方案",
    "全套",
    "步骤",
    "求职",
    "简历",
    "面试",
    "从",
    "到",
    "规划",
    "计划",
    "整理",
    "帮我做",
    "帮我写",
)

_SIMPLE_MEDIA_ANALYSIS_HINTS = (
    "描述",
    "分析",
    "识图",
    "看图",
    "图片",
    "这张图",
    "上图",
    "照片",
    "文件内容",
    "文档内容",
    "总结",
    "讲了什么",
    "是什么",
)


def is_simple_media_analysis_request(message: str) -> bool:
    """短句识图/读文档类需求不需要展开多步计划。"""
    normalized = message.strip()
    if not normalized or len(normalized) > 80:
        return False
    if any(keyword in normalized for keyword in _PLAN_KEYWORDS):
        return False
    return any(hint in normalized for hint in _SIMPLE_MEDIA_ANALYSIS_HINTS)


def should_plan(
    message: str,
    attachment_ids: list[str],
    request: ChatRequest,
    settings: Settings,
) -> bool:
    if not settings.enable_agent_planning:
        return False

    options: RequestOptions = request.options
    if request.enable_planning is False or options.planning_mode == "off":
        return False
    if request.enable_planning is True or options.planning_mode == "always":
        return True

    if attachment_ids:
        if is_simple_media_analysis_request(message):
            return False
        return True
    normalized = message.strip()
    if len(normalized) >= settings.planning_min_message_chars:
        return True
    return any(keyword in normalized for keyword in _PLAN_KEYWORDS)


def format_plan_for_prompt(plan: TaskPlan) -> str:
    lines = [f"总目标：{plan.goal}", "步骤："]
    for index, step in enumerate(plan.steps, start=1):
        lines.append(f"{index}. [{step.id}] {step.title} — {step.description}")
    lines.append(
        "【内部指引】按以上步骤选用工具并完成任务；步骤仅供你内部推进，"
        "禁止在最终回答中逐步骤汇报进度，禁止写「已完成以下步骤」及类似清单。"
        "直接给出用户需要的结论与分析正文。"
    )
    return "\n".join(lines)


class Planner:
    def __init__(self, chat_provider: ChatProvider, settings: Settings) -> None:
        self._chat_provider = chat_provider
        self._settings = settings

    async def create_plan(self, user_message: str, attachment_ids: list[str]) -> TaskPlan:
        attachment_hint = ""
        if attachment_ids:
            attachment_hint = f"\n用户已上传 {len(attachment_ids)} 个附件，ID：{', '.join(attachment_ids)}。"

        system = ChatMessage(
            role="system",
            content=(
                "你是任务规划助手。根据用户需求输出 JSON 对象，字段："
                'goal（字符串）、steps（数组，每项含 id、title、description）。'
                "步骤 2-6 个，id 用 step1/step2 格式，中文，具体可执行。"
                "若仅为描述/分析单个图片或文档，goal 简明，steps 不超过 2 步。"
            ),
        )
        user = ChatMessage(
            role="user",
            content=f"用户需求：{user_message}{attachment_hint}",
        )

        raw = await self._chat_provider.complete_json([system, user], temperature=0)
        goal = str(raw.get("goal") or user_message).strip()
        steps_raw = raw.get("steps")
        steps: list[TaskPlanStep] = []
        if isinstance(steps_raw, list):
            for index, item in enumerate(steps_raw, start=1):
                if not isinstance(item, dict):
                    continue
                step_id = str(item.get("id") or f"step{index}").strip()
                title = str(item.get("title") or f"步骤{index}").strip()
                description = str(item.get("description") or "").strip()
                steps.append(
                    TaskPlanStep(id=step_id, title=title, description=description),
                )

        if not steps:
            steps = [
                TaskPlanStep(
                    id="step1",
                    title="理解需求",
                    description="分析用户目标与约束",
                ),
                TaskPlanStep(
                    id="step2",
                    title="收集信息",
                    description="搜索或解析附件获取必要信息",
                ),
                TaskPlanStep(
                    id="step3",
                    title="产出结果",
                    description="生成用户需要的完整回答或内容",
                ),
            ]

        return TaskPlan(goal=goal, steps=steps)
