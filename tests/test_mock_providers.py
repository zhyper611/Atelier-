import pytest

from app.providers.mock import MockImageProvider


@pytest.mark.asyncio
async def test_mock_image_provider_returns_browser_previewable_url() -> None:
    provider = MockImageProvider()

    result = await provider.generate("赛博朋克城市", "1024x576")

    assert result.url is not None
    assert result.url.startswith("data:image/svg+xml;base64,")
    assert result.metadata["size"] == "1024x576"
