import pytest

from app.agent.schemas import ChatMessage
from app.storage.memory import InMemorySessionStore


@pytest.mark.asyncio
async def test_memory_store_appends_and_reads_session_messages() -> None:
    store = InMemorySessionStore()

    await store.append("demo", ChatMessage(role="user", content="你好"))
    await store.append("demo", ChatMessage(role="assistant", content="你好，我在。"))

    messages = await store.get("demo")

    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "你好"


@pytest.mark.asyncio
async def test_memory_store_append_many() -> None:
    store = InMemorySessionStore()
    await store.append_many(
        "demo",
        [
            ChatMessage(role="user", content="你好"),
            ChatMessage(role="tool", content="obs", tool_call_id="c1"),
            ChatMessage(role="assistant", content="回复"),
        ],
    )

    messages = await store.get("demo")
    assert len(messages) == 3
    assert messages[1].role == "tool"


@pytest.mark.asyncio
async def test_memory_store_clears_a_session() -> None:
    store = InMemorySessionStore()
    await store.append("demo", ChatMessage(role="user", content="清空前"))

    deleted = await store.clear("demo")

    assert deleted is True
    assert await store.get("demo") == []
