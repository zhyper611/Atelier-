import pytest

try:
    from fakeredis.aioredis import FakeRedis
except ImportError:
    FakeRedis = None  # type: ignore[misc, assignment]

from app.agent.schemas import ChatMessage
from app.storage.redis_store import RedisSessionStore


@pytest.mark.asyncio
@pytest.mark.skipif(FakeRedis is None, reason="fakeredis not installed")
async def test_redis_store_roundtrip() -> None:
    client = FakeRedis(decode_responses=True)
    store = RedisSessionStore(client, session_ttl_seconds=60)

    await store.append_many(
        "demo",
        [
            ChatMessage(role="user", content="你好"),
            ChatMessage(role="tool", content="摘要", tool_call_id="c1"),
            ChatMessage(role="assistant", content="回复", run_id="run-1"),
        ],
    )

    messages = await store.get("demo")
    assert len(messages) == 3
    assert messages[2].run_id == "run-1"

    deleted = await store.clear("demo")
    assert deleted is True
    assert await store.get("demo") == []

    await client.aclose()
