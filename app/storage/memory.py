from collections import defaultdict
from collections.abc import Sequence

from app.agent.schemas import ChatMessage


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, list[ChatMessage]] = defaultdict(list)

    async def get(self, session_id: str) -> list[ChatMessage]:
        return list(self._sessions.get(session_id, []))

    async def append(self, session_id: str, message: ChatMessage) -> None:
        self._sessions[session_id].append(message)

    async def append_many(self, session_id: str, messages: Sequence[ChatMessage]) -> None:
        if messages:
            self._sessions[session_id].extend(messages)

    async def clear(self, session_id: str) -> bool:
        existed = session_id in self._sessions
        self._sessions.pop(session_id, None)
        return existed
