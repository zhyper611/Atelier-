import httpx
import pytest

from app.agent.tools.url_fetcher import (
    UrlFetchError,
    coerce_urls,
    fetch_and_extract,
    format_fetch_observation,
    humanize_http_error,
    normalize_url_for_fetch,
    validate_url,
)
import httpx
from app.core.config import Settings

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test Report</title></head>
<body>
<article>
<h1>Market Outlook</h1>
<p>Revenue grew 12 percent year over year in the first quarter.</p>
<p>Analysts expect continued expansion in cloud services.</p>
</article>
</body>
</html>
"""


@pytest.fixture
def settings() -> Settings:
    return Settings(
        fetch_url_enabled=True,
        fetch_url_timeout_seconds=10,
        fetch_url_max_bytes=1_000_000,
        fetch_url_max_content_chars=5000,
        fetch_url_blocked_domains="localhost,127.0.0.1,blocked.test",
    )


def test_validate_url_rejects_private_and_file_scheme(settings: Settings) -> None:
    with pytest.raises(UrlFetchError):
        validate_url("file:///etc/passwd", settings)
    with pytest.raises(UrlFetchError):
        validate_url("http://127.0.0.1/page", settings)
    with pytest.raises(UrlFetchError):
        validate_url("http://192.168.1.10/internal", settings)
    with pytest.raises(UrlFetchError):
        validate_url("https://blocked.test/article", settings)


def test_validate_url_accepts_public_https(settings: Settings) -> None:
    assert validate_url("https://Example.com/Report?id=1", settings).startswith("https://")


def test_normalize_url_encodes_idn_host() -> None:
    encoded = normalize_url_for_fetch("https://www.测试.com/path")
    assert "xn--" in encoded
    assert "测试" not in encoded


def test_humanize_connect_error_message() -> None:
    msg = humanize_http_error(httpx.ConnectError(""))
    assert "无法连接" in msg
    assert msg != "网络请求失败："


def test_coerce_urls_dedupes() -> None:
    urls = coerce_urls(["https://a.com", "https://a.com"], "https://b.com")
    assert urls == ["https://a.com", "https://b.com"]


@pytest.mark.asyncio
async def test_fetch_and_extract_html(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SAMPLE_HTML, headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_and_extract("https://news.example.com/report", settings, client=client)

    assert result.error is None
    assert "Revenue" in result.text or "Market" in result.text
    assert result.char_count > 0


@pytest.mark.asyncio
async def test_fetch_and_extract_rejects_oversized_body(settings: Settings) -> None:
    huge = b"x" * 2000

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=huge, headers={"content-type": "text/plain"})

    transport = httpx.MockTransport(handler)
    tiny_settings = settings.model_copy(update={"fetch_url_max_bytes": 500})
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(UrlFetchError, match="超过"):
            await fetch_and_extract("https://news.example.com/big", tiny_settings, client=client)


@pytest.mark.asyncio
async def test_fetch_and_extract_plain_text(settings: Settings) -> None:
    body = "Plain document body for testing."

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body, headers={"content-type": "text/plain"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_and_extract("https://news.example.com/doc.txt", settings, client=client)

    assert "Plain document" in result.text


def test_format_fetch_observation() -> None:
    from app.agent.tools.url_fetcher import FetchPageResult

    text = format_fetch_observation(
        [
            FetchPageResult(
                url="https://a.com",
                title="A",
                text="body",
                char_count=4,
                truncated=False,
            ),
            FetchPageResult(
                url="https://b.com",
                title="",
                text="",
                char_count=0,
                truncated=False,
                error="HTTP 403",
            ),
        ],
    )
    assert "[1] https://a.com" in text
    assert "错误：HTTP 403" in text
