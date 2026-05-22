from __future__ import annotations

import httpx

from app.agent.schemas import ToolResult
from app.core.config import Settings
from app.providers.ark_client import (
    ArkApiError,
    extract_image_url,
    request_json,
    resolve_api_key,
)
from app.providers.image_size import normalize_image_size


class ArkImageProvider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client
        self._api_key = resolve_api_key(settings, preferred=settings.image_api_key)
        if not settings.image_api_base_url:
            raise ArkApiError("IMAGE_API_BASE_URL is not configured")

    async def generate(self, prompt: str, size: str) -> ToolResult:
        requested_size = size
        api_size = normalize_image_size(size)
        payload = {
            "model": self._settings.image_model,
            "prompt": prompt,
            "size": api_size,
            "response_format": self._settings.image_response_format,
            "watermark": self._settings.image_watermark,
        }

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        try:
            response = await request_json(
                client,
                "POST",
                self._settings.image_api_base_url,
                api_key=self._api_key,
                json_body=payload,
            )
            image_url = extract_image_url(response)
            return ToolResult(
                type="image",
                url=image_url,
                metadata={
                    "prompt": prompt,
                    "size": api_size,
                    "requested_size": requested_size,
                    "model": self._settings.image_model,
                    "provider": "ark",
                },
            )
        finally:
            if owns_client:
                await client.aclose()
