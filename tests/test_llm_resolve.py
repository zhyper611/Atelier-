from app.core.config import Settings
from app.providers.llm_resolve import (
    DEFAULT_ARK_CHAT_BASE,
    resolve_chat_api_key,
    resolve_chat_base_url,
    resolve_chat_model,
)


def test_resolve_chat_from_ark_fallback() -> None:
    settings = Settings(
        llm_api_base_url=None,
        llm_api_key=None,
        video_api_base_url="https://ark.cn-beijing.volces.com/api/v3",
        ark_api_key="test-ark-key",
    )
    assert resolve_chat_base_url(settings) == "https://ark.cn-beijing.volces.com/api/v3"
    assert resolve_chat_api_key(settings) == "test-ark-key"
    assert "doubao-seed" in resolve_chat_model(settings)


def test_resolve_chat_model_prefers_endpoint_id() -> None:
    settings = Settings(
        ark_chat_endpoint_id="ep-test-123",
        llm_model="doubao-seed-2-0-lite-260215",
    )
    assert resolve_chat_model(settings) == "ep-test-123"


def test_resolve_chat_base_explicit() -> None:
    settings = Settings(llm_api_base_url="https://custom.example/v1")
    assert resolve_chat_base_url(settings) == "https://custom.example/v1"
    assert resolve_chat_base_url(Settings()) == DEFAULT_ARK_CHAT_BASE
