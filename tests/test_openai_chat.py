import json

import httpx
import pytest

from app.core.config import Settings
from app.providers.openai_chat import OpenAIChatProvider


def _settings() -> Settings:
    return Settings(
        llm_api_base_url="http://llm.example.com/v1",
        llm_api_key="test-llm-key",
        llm_model="ClawClaw",
    )


@pytest.mark.asyncio
async def test_openai_chat_provider_complete() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "ClawClaw"
        assert body["messages"][-1]["content"] == "你好"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "你好，有什么可以帮你？"}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAIChatProvider(_settings(), client=client)

    from app.agent.schemas import ChatMessage

    answer = await provider.complete([ChatMessage(role="user", content="你好")])

    assert answer == "你好，有什么可以帮你？"


@pytest.mark.asyncio
async def test_openai_chat_provider_stream() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["stream"] is True
        lines = [
            'data: {"choices":[{"delta":{"content":"你"}}]}',
            'data: {"choices":[{"delta":{"content":"好"}}]}',
            "data: [DONE]",
        ]
        content = "\n".join(lines) + "\n"
        return httpx.Response(200, content=content)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAIChatProvider(_settings(), client=client)

    from app.agent.schemas import ChatMessage

    chunks = [
        chunk
        async for chunk in provider.stream_complete([ChatMessage(role="user", content="你好")])
    ]

    assert "".join(chunks) == "你好"
