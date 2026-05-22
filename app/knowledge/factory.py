from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import Settings
from app.knowledge.store import KnowledgeStore


async def build_knowledge_store(settings: Settings) -> KnowledgeStore | None:
    if not settings.knowledge_enabled:
        return None
    client = Redis.from_url(
        settings.resolved_knowledge_redis_url(),
        decode_responses=False,
    )
    store = KnowledgeStore(client, settings)
    try:
        await store.ensure_index()
    except Exception:
        await client.aclose()
        return None
    return store


async def close_knowledge_store(store: KnowledgeStore | None) -> None:
    if store is None:
        return
    await store._redis.aclose()  # noqa: SLF001
