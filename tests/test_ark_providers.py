import json

import httpx
import pytest

from app.core.config import Settings
from app.providers.ark_image import ArkImageProvider
from app.providers.ark_video import ArkVideoProvider


def _settings() -> Settings:
    return Settings(
        image_api_base_url="https://ark.example.com/api/v3/images/generations",
        image_api_key="test-image-key",
        image_model="doubao-seedream-test",
        image_response_format="url",
        image_watermark=False,
        video_tasks_url="https://ark.example.com/api/v3/contents/generations/tasks",
        video_task_status_url_template="https://ark.example.com/api/v3/contents/generations/tasks/{task_id}",
        video_api_key="test-video-key",
        video_model="doubao-seedance-test",
        video_ratio="16:9",
        video_resolution="720p",
        video_watermark=False,
        video_poll_interval_seconds=1,
        video_poll_timeout_seconds=10,
    )


@pytest.mark.asyncio
async def test_ark_image_provider_parses_image_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.headers["authorization"] == "Bearer test-image-key"
        body = json.loads(request.content)
        assert body["prompt"] == "cyberpunk city"
        assert body["size"] == "2560x1440"
        return httpx.Response(
            200,
            json={"data": [{"url": "https://cdn.example.com/generated.png", "size": "2560x1440"}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    provider = ArkImageProvider(_settings(), client=client)

    result = await provider.generate("cyberpunk city", "1024x576")

    assert result.type == "image"
    assert result.url == "https://cdn.example.com/generated.png"
    assert result.metadata["provider"] == "ark"


@pytest.mark.asyncio
async def test_ark_video_provider_polls_until_success() -> None:
    calls = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"id": "cgt-test-001", "status": "queued"})
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(200, json={"id": "cgt-test-001", "status": "running"})
        return httpx.Response(
            200,
            json={
                "id": "cgt-test-001",
                "status": "succeeded",
                "content": {"video_url": "https://cdn.example.com/video.mp4"},
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    provider = ArkVideoProvider(_settings(), client=client)

    result = await provider.generate("sunset beach", "1280x720", 5)

    assert result.type == "video"
    assert result.url == "https://cdn.example.com/video.mp4"
    assert result.metadata["task_id"] == "cgt-test-001"


@pytest.mark.asyncio
async def test_ark_video_provider_sends_reference_image_for_image_to_video() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["ratio"] == "adaptive"
            assert body["content"] == [
                {"type": "text", "text": "让角色转头微笑"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://cdn.example.com/frame.png"},
                },
            ]
            return httpx.Response(200, json={"id": "cgt-test-002", "status": "succeeded", "content": {"video_url": "https://cdn.example.com/video.mp4"}})

        return httpx.Response(200, json={"id": "cgt-test-002", "status": "succeeded", "content": {"video_url": "https://cdn.example.com/video.mp4"}})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    provider = ArkVideoProvider(_settings(), client=client)

    result = await provider.generate(
        "让角色转头微笑",
        "1280x720",
        5,
        reference_image_url="https://cdn.example.com/frame.png",
    )

    assert result.metadata["mode"] == "image_to_video"
    assert result.metadata["reference_image_url"] == "https://cdn.example.com/frame.png"
