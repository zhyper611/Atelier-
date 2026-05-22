import pytest

from app.providers.ark_client import ArkApiError
from app.providers.volc_search import _parse_web_search_response


def test_parse_web_search_response_builds_summary_and_sources() -> None:
    payload = {
        "ResponseMetadata": {"RequestId": "req-1"},
        "Result": {
            "WebResults": [
                {
                    "Title": "AI 新闻",
                    "Summary": "今日 AI 行业动态摘要。",
                    "Url": "https://example.com/ai",
                },
                {
                    "Title": "科技速递",
                    "Summary": "更多科技资讯。",
                    "Url": "https://example.com/tech",
                },
            ]
        },
    }

    result = _parse_web_search_response("今天 AI 新闻", payload)

    assert result.query == "今天 AI 新闻"
    assert "AI 新闻" in result.summary
    assert result.sources == ["https://example.com/ai", "https://example.com/tech"]


def test_parse_web_search_response_raises_on_api_error() -> None:
    payload = {
        "ResponseMetadata": {
            "Error": {"Code": "invalid_api_key", "Message": "invalid api key"},
        },
        "Result": None,
    }

    with pytest.raises(ArkApiError, match="invalid api key"):
        _parse_web_search_response("test", payload)
