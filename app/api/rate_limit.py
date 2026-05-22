from __future__ import annotations

import time
from collections import defaultdict
from typing import Protocol

from redis.asyncio import Redis


class RateLimiter(Protocol):
    async def check(self, session_id: str) -> bool:
        """Return True if request is allowed."""

    async def close(self) -> None:
        ...


class InMemoryRateLimiter:
    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def check(self, session_id: str) -> bool:
        now = time.monotonic()
        window_start = now - self._window_seconds
        timestamps = [ts for ts in self._buckets[session_id] if ts > window_start]
        if len(timestamps) >= self._max_requests:
            self._buckets[session_id] = timestamps
            return False
        timestamps.append(now)
        self._buckets[session_id] = timestamps
        return True

    async def close(self) -> None:
        self._buckets.clear()


class RedisRateLimiter:
    def __init__(
        self,
        client: Redis,
        *,
        max_requests: int,
        window_seconds: int,
    ) -> None:
        self._client = client
        self._max_requests = max_requests
        self._window_seconds = window_seconds

    def _key(self, session_id: str) -> str:
        return f"agent:ratelimit:{session_id}"

    async def check(self, session_id: str) -> bool:
        key = self._key(session_id)
        count = await self._client.incr(key)
        if count == 1:
            await self._client.expire(key, self._window_seconds)
        return int(count) <= self._max_requests

    async def close(self) -> None:
        await self._client.aclose()


async def build_rate_limiter(
    *,
    session_store: str,
    redis_url: str,
    max_requests: int,
    window_seconds: int,
) -> RateLimiter:
    if session_store == "redis":
        client = Redis.from_url(redis_url, decode_responses=True)
        await client.ping()
        return RedisRateLimiter(
            client,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )
    return InMemoryRateLimiter(
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
