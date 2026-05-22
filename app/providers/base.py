from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol

from app.agent.react.schemas import LlmTurn
from app.agent.schemas import ChatMessage, SearchResult, ToolResult


class ChatProvider(Protocol):
    async def complete(
        self,
        messages: Sequence[ChatMessage],
        search_context: SearchResult | None = None,
    ) -> str:
        ...

    async def complete_with_tools(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
    ) -> LlmTurn:
        ...

    async def stream_complete(
        self,
        messages: Sequence[ChatMessage],
        search_context: SearchResult | None = None,
    ) -> AsyncIterator[str]:
        ...

    async def stream_working_messages(
        self,
        messages: Sequence[dict[str, Any]],
    ) -> AsyncIterator[str]:
        ...

    async def complete_json(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0,
    ) -> dict[str, Any]:
        ...

    async def describe_image(self, prompt: str, image_data_url: str) -> str:
        ...


class SearchProvider(Protocol):
    async def search(self, query: str) -> SearchResult:
        ...


class ImageProvider(Protocol):
    async def generate(self, prompt: str, size: str) -> ToolResult:
        ...


class VideoProvider(Protocol):
    async def generate(
        self,
        prompt: str,
        size: str,
        duration_seconds: int,
        reference_image_url: str | None = None,
    ) -> ToolResult:
        ...
