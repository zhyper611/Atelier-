from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.agent.schemas import ChatMessage


class SessionStore(Protocol):
    async def get(self, session_id: str) -> list[ChatMessage]: ...

    async def append(self, session_id: str, message: ChatMessage) -> None: ...

    async def append_many(self, session_id: str, messages: Sequence[ChatMessage]) -> None: ...

    async def clear(self, session_id: str) -> bool: ...
