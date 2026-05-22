import base64
import html
from collections.abc import AsyncIterator, Sequence
from typing import Any

from app.agent.react.schemas import LlmTurn, ToolCallRequest
from app.agent.schemas import ChatMessage, RequestOptions, SearchResult, ToolResult
from app.agent.tools.mock_routing import decide_mock_tool_calls, mock_final_content


class MockChatProvider:
    def __init__(self, options: RequestOptions | None = None) -> None:
        self._options = options or RequestOptions()

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        search_context: SearchResult | None = None,
    ) -> str:
        latest_user_message = next(
            (message.content for message in reversed(messages) if message.role == "user"),
            "",
        )
        if search_context is not None:
            return f"搜索结果显示：{search_context.summary}"
        return f"你说的是：{latest_user_message}"

    async def complete_with_tools(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
    ) -> LlmTurn:
        del tools
        tool_calls_raw = decide_mock_tool_calls(messages, self._options)
        if tool_calls_raw:
            tool_calls = [
                ToolCallRequest(
                    id=item["id"],
                    name=item["function"]["name"],
                    arguments=item["function"]["arguments"],
                )
                for item in tool_calls_raw
            ]
            return LlmTurn(tool_calls=tool_calls, finish_reason="tool_calls")

        content = mock_final_content(messages)
        return LlmTurn(content=content, finish_reason="stop")

    async def stream_complete(
        self,
        messages: Sequence[ChatMessage],
        search_context: SearchResult | None = None,
    ) -> AsyncIterator[str]:
        answer = await self.complete(messages, search_context)
        for part in answer.split(" "):
            if part:
                yield part + " "

    async def stream_working_messages(
        self,
        messages: Sequence[dict[str, Any]],
    ) -> AsyncIterator[str]:
        from app.agent.tools.mock_routing import mock_final_content

        answer = mock_final_content(messages)
        chunk_size = 4
        for index in range(0, len(answer), chunk_size):
            yield answer[index : index + chunk_size]

    async def complete_working_messages(
        self,
        messages: Sequence[dict[str, Any]],
    ) -> str:
        from app.agent.tools.mock_routing import mock_final_content

        return mock_final_content(messages)

    async def complete_json(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0,
    ) -> dict[str, Any]:
        del messages, temperature
        return {
            "goal": "完成用户请求的模拟任务",
            "steps": [
                {
                    "id": "step1",
                    "title": "理解需求",
                    "description": "分析用户目标与约束",
                },
                {
                    "id": "step2",
                    "title": "收集信息",
                    "description": "搜索或解析附件",
                },
                {
                    "id": "step3",
                    "title": "产出结果",
                    "description": "生成完整回答",
                },
            ],
        }

    async def describe_image(self, prompt: str, image_data_url: str) -> str:
        del image_data_url
        return f"【模拟识图】{prompt} — 画面中可见示例图形与文字（mock）。"



class MockSearchProvider:
    async def search(self, query: str) -> SearchResult:
        return SearchResult(
            query=query,
            summary=f"这是关于“{query}”的模拟搜索摘要，真实联网搜索 API 可在这里接入。",
            sources=["mock://search/result/1"],
        )


def _parse_dimensions(size: str) -> tuple[int, int]:
    normalized = size.lower().replace("*", "x").replace("×", "x")
    if "x" not in normalized:
        return 1024, 1024
    width_text, height_text = normalized.split("x", 1)
    try:
        width = max(64, int(width_text))
        height = max(64, int(height_text))
    except ValueError:
        return 1024, 1024
    return width, height


def _placeholder_image_data_url(prompt: str, size: str) -> str:
    width, height = _parse_dimensions(size)
    safe_prompt = html.escape(prompt[:80])
    safe_size = html.escape(size)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0b1020"/>
      <stop offset="55%" stop-color="#1a1440"/>
      <stop offset="100%" stop-color="#2b1b3d"/>
    </linearGradient>
    <linearGradient id="glow" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#00d4ff" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="#d4af6a" stop-opacity="0.35"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#bg)"/>
  <rect width="100%" height="100%" fill="url(#glow)"/>
  <text x="50%" y="42%" text-anchor="middle" fill="#d4af6a" font-family="sans-serif" font-size="{max(18, width // 40)}">Mock Generated Image</text>
  <text x="50%" y="52%" text-anchor="middle" fill="#9aa3b2" font-family="sans-serif" font-size="{max(12, width // 55)}">{safe_size}</text>
  <text x="50%" y="62%" text-anchor="middle" fill="#c7d0dd" font-family="sans-serif" font-size="{max(11, width // 60)}">{safe_prompt}</text>
</svg>"""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _placeholder_video_url(size: str) -> str:
    width, height = _parse_dimensions(size)
    # Public sample clip for mock video preview in the browser.
    return f"https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4#{width}x{height}"


class MockImageProvider:
    async def generate(self, prompt: str, size: str) -> ToolResult:
        return ToolResult(
            type="image",
            url=_placeholder_image_data_url(prompt, size),
            metadata={"prompt": prompt, "size": size, "mock": True},
        )


class MockVideoProvider:
    async def generate(
        self,
        prompt: str,
        size: str,
        duration_seconds: int,
        reference_image_url: str | None = None,
    ) -> ToolResult:
        return ToolResult(
            type="video",
            url=_placeholder_video_url(size),
            metadata={
                "prompt": prompt,
                "size": size,
                "duration_seconds": duration_seconds,
                "reference_image_url": reference_image_url,
                "mode": "image_to_video" if reference_image_url else "text_to_video",
                "mock": True,
            },
        )
