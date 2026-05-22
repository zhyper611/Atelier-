from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from app.agent.react.messages import (
    collapse_messages_for_streaming_completion,
    normalize_messages_for_api,
)
from app.agent.react.schemas import LlmTurn, ToolCallRequest
from app.agent.schemas import ChatMessage, SearchResult
from app.core.config import Settings
from app.providers.ark_client import ArkApiError, build_headers
from app.providers.llm_resolve import (
    resolve_chat_api_key,
    resolve_chat_base_url,
    resolve_chat_model,
    resolve_vision_model,
)


class OpenAIChatProvider:
    """OpenAI-compatible chat completions (SpiritX / vLLM / 方舟等)."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._api_key = resolve_chat_api_key(settings)
        base = resolve_chat_base_url(settings)
        self._chat_url = f"{base}/chat/completions"
        self._chat_model = resolve_chat_model(settings)
        self._vision_model = resolve_vision_model(settings)
        self._llm_timeout = httpx.Timeout(float(settings.llm_timeout_seconds))
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=self._llm_timeout)

    def _api_messages_for_final(self, messages: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        return collapse_messages_for_streaming_completion(
            messages,
            max_tool_context_chars=self._settings.final_tool_context_max_chars,
        )

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        search_context: SearchResult | None = None,
    ) -> str:
        payload = self._build_payload(messages, search_context, stream=False)
        response = await self._client.post(
            self._chat_url,
            headers=build_headers(self._api_key),
            json=payload,
        )
        data = self._parse_response_json(response)
        return self._extract_message_content(data)

    async def complete_json(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0,
    ) -> dict[str, Any]:
        api_messages: list[dict[str, str]] = []
        for message in messages:
            if message.role in {"user", "assistant", "system"}:
                api_messages.append({"role": message.role, "content": message.content})

        payload = {
            "model": self._chat_model,
            "messages": api_messages,
            "stream": False,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        response = await self._client.post(
            self._chat_url,
            headers=build_headers(self._api_key),
            json=payload,
        )
        data = self._parse_response_json(response)
        content = self._extract_message_content(data)
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ArkApiError("LLM JSON response is not an object", payload=data)
        return parsed

    async def complete_with_tools(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
    ) -> LlmTurn:
        payload = {
            "model": self._chat_model,
            "messages": normalize_messages_for_api(messages),
            "tools": list(tools),
            "stream": False,
        }

        response = await self._client.post(
            self._chat_url,
            headers=build_headers(self._api_key),
            json=payload,
        )
        data = self._parse_response_json(response)
        return self._extract_llm_turn(data)

    async def complete_working_messages(
        self,
        messages: Sequence[dict[str, Any]],
    ) -> str:
        api_messages = self._api_messages_for_final(messages)
        payload = {
            "model": self._chat_model,
            "messages": api_messages,
            "stream": False,
        }
        response = await self._client.post(
            self._chat_url,
            headers=build_headers(self._api_key),
            json=payload,
        )
        data = self._parse_response_json(response)
        return self._extract_message_content(data)

    async def describe_image(self, prompt: str, image_data_url: str) -> str:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            },
        ]
        payload = {
            "model": self._vision_model,
            "messages": messages,
            "stream": False,
        }
        response = await self._client.post(
            self._chat_url,
            headers=build_headers(self._api_key),
            json=payload,
        )
        data = self._parse_response_json(response)
        return self._extract_message_content(data)

    async def _stream_working_messages_once(
        self,
        messages: Sequence[dict[str, Any]],
    ) -> AsyncIterator[str]:
        api_messages = self._api_messages_for_final(messages)
        payload = {
            "model": self._chat_model,
            "messages": api_messages,
            "stream": True,
        }
        async with self._client.stream(
            "POST",
            self._chat_url,
            headers=build_headers(self._api_key),
            json=payload,
        ) as response:
            if response.status_code >= 400:
                body = await response.aread()
                detail = body.decode("utf-8", errors="replace").strip()
                raise ArkApiError(
                    f"LLM stream HTTP {response.status_code}: {detail or 'request failed'}",
                    status_code=response.status_code,
                )
            async for line in response.aiter_lines():
                chunk = self._parse_stream_line(line)
                if chunk:
                    yield chunk

    async def stream_working_messages(
        self,
        messages: Sequence[dict[str, Any]],
    ) -> AsyncIterator[str]:
        last_exc: BaseException | None = None
        for attempt in range(3):
            try:
                async for chunk in self._stream_working_messages_once(messages):
                    yield chunk
                return
            except httpx.ConnectError as exc:
                last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                break

        try:
            text = await self.complete_working_messages(messages)
        except Exception as exc:
            if last_exc is not None:
                raise last_exc from exc
            raise

        chunk_size = 12
        for index in range(0, len(text), chunk_size):
            yield text[index : index + chunk_size]

    async def stream_complete(
        self,
        messages: Sequence[ChatMessage],
        search_context: SearchResult | None = None,
    ) -> AsyncIterator[str]:
        payload = self._build_payload(messages, search_context, stream=True)
        async with self._client.stream(
            "POST",
            self._chat_url,
            headers=build_headers(self._api_key),
            json=payload,
        ) as response:
            if response.status_code >= 400:
                body = await response.aread()
                detail = body.decode("utf-8", errors="replace").strip()
                message = detail or "LLM stream request failed"
                raise ArkApiError(
                    f"LLM stream HTTP {response.status_code}: {message}",
                    status_code=response.status_code,
                )

            async for line in response.aiter_lines():
                chunk = self._parse_stream_line(line)
                if chunk:
                    yield chunk

    def _build_payload(
        self,
        messages: Sequence[ChatMessage],
        search_context: SearchResult | None,
        *,
        stream: bool,
    ) -> dict:
        api_messages: list[dict[str, str]] = []
        if search_context is not None:
            sources = "\n".join(search_context.sources) if search_context.sources else "无"
            api_messages.append(
                {
                    "role": "system",
                    "content": (
                        "以下是联网搜索摘要，请基于其回答用户问题。\n"
                        f"摘要：{search_context.summary}\n"
                        f"来源：{sources}"
                    ),
                }
            )

        for message in messages:
            if message.role in {"user", "assistant", "system"}:
                api_messages.append({"role": message.role, "content": message.content})

        return {
            "model": self._chat_model,
            "messages": api_messages,
            "stream": stream,
        }

    def _parse_response_json(self, response: httpx.Response) -> dict:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ArkApiError(
                f"Invalid JSON from LLM API ({response.status_code})",
                status_code=response.status_code,
            ) from exc

        if response.status_code >= 400:
            message = payload.get("error", {}).get("message") if isinstance(payload.get("error"), dict) else response.text
            raise ArkApiError(str(message), status_code=response.status_code, payload=payload)

        if not isinstance(payload, dict):
            raise ArkApiError("Unexpected LLM API response format")
        return payload

    def _extract_llm_turn(self, payload: dict) -> LlmTurn:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ArkApiError("LLM API response did not include choices", payload=payload)

        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ArkApiError("LLM API response did not include message", payload=payload)

        content = message.get("content")
        text_content = content if isinstance(content, str) and content.strip() else None

        raw_tool_calls = message.get("tool_calls")
        tool_calls: list[ToolCallRequest] = []
        if isinstance(raw_tool_calls, list):
            for item in raw_tool_calls:
                if not isinstance(item, dict):
                    continue
                function = item.get("function")
                if not isinstance(function, dict):
                    continue
                name = function.get("name")
                arguments = function.get("arguments")
                call_id = item.get("id")
                if isinstance(name, str) and isinstance(arguments, str) and isinstance(call_id, str):
                    tool_calls.append(
                        ToolCallRequest(id=call_id, name=name, arguments=arguments),
                    )

        finish_reason = choices[0].get("finish_reason")
        return LlmTurn(
            content=text_content,
            tool_calls=tool_calls,
            finish_reason=finish_reason if isinstance(finish_reason, str) else None,
        )

    def _extract_message_content(self, payload: dict) -> str:
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content

        output = payload.get("output")
        if isinstance(output, str) and output.strip():
            return output

        raise ArkApiError("LLM API response did not include message content", payload=payload)

    def _parse_stream_line(self, line: str) -> str | None:
        stripped = line.strip()
        if not stripped or not stripped.startswith("data:"):
            return None

        data = stripped.removeprefix("data:").strip()
        if data == "[DONE]":
            return None

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return None

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None

        delta = choices[0].get("delta")
        if isinstance(delta, dict):
            content = delta.get("content")
            if isinstance(content, str) and content:
                return content

        message = choices[0].get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content:
                return content

        return None
