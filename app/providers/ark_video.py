from __future__ import annotations

import asyncio

import httpx

from app.agent.schemas import ToolResult
from app.core.config import Settings
from app.providers.ark_client import (
    ArkApiError,
    extract_task_id,
    extract_task_status,
    extract_video_url,
    is_success_status,
    is_terminal_status,
    request_json,
    resolve_api_key,
)


class ArkVideoProvider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client
        self._api_key = resolve_api_key(settings, preferred=settings.video_api_key)
        if not settings.video_tasks_url:
            raise ArkApiError("VIDEO_TASKS_URL is not configured")
        if not settings.video_task_status_url_template:
            raise ArkApiError("VIDEO_TASK_STATUS_URL_TEMPLATE is not configured")

    async def generate(
        self,
        prompt: str,
        size: str,
        duration_seconds: int,
        reference_image_url: str | None = None,
    ) -> ToolResult:
        ratio = self._settings.video_ratio or self._ratio_from_size(size)
        duration = max(2, min(duration_seconds, 12))

        content: list[dict] = [{"type": "text", "text": prompt}]
        if reference_image_url:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": reference_image_url},
                }
            )
            ratio = "adaptive"

        create_payload = {
            "model": self._settings.video_model,
            "content": content,
            "ratio": ratio,
            "duration": duration,
            "resolution": self._settings.video_resolution,
            "watermark": self._settings.video_watermark,
        }

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        try:
            created = await request_json(
                client,
                "POST",
                self._settings.video_tasks_url,
                api_key=self._api_key,
                json_body=create_payload,
            )
            task_id = extract_task_id(created)
            status_url = self._settings.video_task_status_url_template.format(task_id=task_id)

            deadline = asyncio.get_running_loop().time() + self._settings.video_poll_timeout_seconds
            interval = self._settings.video_poll_interval_seconds
            last_payload: dict = created

            while True:
                last_payload = await request_json(
                    client,
                    "GET",
                    status_url,
                    api_key=self._api_key,
                )
                status = extract_task_status(last_payload)
                if is_success_status(status):
                    video_url = extract_video_url(last_payload)
                    if not video_url:
                        raise ArkApiError(
                            "Video task succeeded but no video URL was returned",
                            payload=last_payload,
                        )
                    return ToolResult(
                        type="video",
                        url=video_url,
                        metadata={
                            "prompt": prompt,
                            "size": size,
                            "duration_seconds": duration,
                            "ratio": ratio,
                            "resolution": self._settings.video_resolution,
                            "model": self._settings.video_model,
                            "task_id": task_id,
                            "provider": "ark",
                            "reference_image_url": reference_image_url,
                            "mode": "image_to_video" if reference_image_url else "text_to_video",
                        },
                    )

                if is_terminal_status(status) and not is_success_status(status):
                    message = last_payload.get("error")
                    if isinstance(message, dict):
                        message = message.get("message")
                    if not isinstance(message, str):
                        message = f"Video generation failed with status: {status}"
                    raise ArkApiError(message, payload=last_payload)

                if asyncio.get_running_loop().time() >= deadline:
                    raise ArkApiError(
                        f"Video generation timed out after {self._settings.video_poll_timeout_seconds}s",
                        payload=last_payload,
                    )

                await asyncio.sleep(interval)
        finally:
            if owns_client:
                await client.aclose()

    def _ratio_from_size(self, size: str) -> str:
        normalized = size.lower().replace("*", "x").replace("×", "x")
        if "x" not in normalized:
            return self._settings.video_ratio
        width_text, height_text = normalized.split("x", 1)
        try:
            width = int(width_text)
            height = int(height_text)
        except ValueError:
            return self._settings.video_ratio
        if width <= 0 or height <= 0:
            return self._settings.video_ratio

        from math import gcd

        divisor = gcd(width, height)
        return f"{width // divisor}:{height // divisor}"
