from __future__ import annotations

from collections.abc import Sequence

from redis.asyncio import Redis

from app.agent.schemas import ChatMessage


def _session_key(session_id: str) -> str:
    return f"agent:session:{session_id}:messages"


class RedisSessionStore:
    def __init__(
        self,
        client: Redis,
        *,
        session_ttl_seconds: int = 0,
    ) -> None:
        self._client = client
        self._session_ttl_seconds = session_ttl_seconds

    async def get(self, session_id: str) -> list[ChatMessage]:
        key = _session_key(session_id)
        raw_items = await self._client.lrange(key, 0, -1)
        return [ChatMessage.model_validate_json(item) for item in raw_items]

    async def append(self, session_id: str, message: ChatMessage) -> None:
        await self.append_many(session_id, [message])

    async def append_many(self, session_id: str, messages: Sequence[ChatMessage]) -> None:
        if not messages:
            return
        key = _session_key(session_id)
        payload = [message.model_dump_json() for message in messages]
        await self._client.rpush(key, *payload)
        if self._session_ttl_seconds > 0:
            await self._client.expire(key, self._session_ttl_seconds)

    async def clear(self, session_id: str) -> bool:
        key = _session_key(session_id)
        deleted = await self._client.delete(key)
        return deleted > 0
