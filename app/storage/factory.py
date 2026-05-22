from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis

from app.core.config import Settings
from app.storage.base import SessionStore
from app.storage.memory import InMemorySessionStore
from app.storage.redis_store import RedisSessionStore


@asynccontextmanager
async def session_store_lifespan(settings: Settings) -> AsyncIterator[tuple[SessionStore, Redis | None]]:
    if settings.session_store == "redis":
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        store = RedisSessionStore(
            client,
            session_ttl_seconds=settings.session_ttl_seconds,
        )
        try:
            yield store, client
        finally:
            await client.aclose()
    else:
        yield InMemorySessionStore(), None
