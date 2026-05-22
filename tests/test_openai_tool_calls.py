import json

import httpx
import pytest

from app.core.config import Settings
from app.providers.openai_chat import OpenAIChatProvider


@pytest.mark.asyncio
async def test_complete_with_tools_sends_tools_and_parses_tool_calls() -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured["tools"] = body.get("tools")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_abc",
                                    "type": "function",
                                    "function": {
                                        "name": "web_search",
                                        "arguments": json.dumps({"query": "AI news"}),
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        )

    settings = Settings(
        llm_api_base_url="https://llm.example.com/v1",
        llm_api_key="test-key",
        llm_model="test-model",
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAIChatProvider(settings, client=client)

    turn = await provider.complete_with_tools(
        [{"role": "user", "content": "今天有什么新闻？"}],
        [{"type": "function", "function": {"name": "web_search"}}],
    )

    assert captured["tools"] is not None
    assert turn.has_tool_calls
    assert turn.tool_calls[0].name == "web_search"
    assert json.loads(turn.tool_calls[0].arguments)["query"] == "AI news"
