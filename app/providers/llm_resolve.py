from __future__ import annotations

from app.core.config import Settings
from app.providers.ark_client import ArkApiError

DEFAULT_ARK_CHAT_BASE = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_DOUBAO_SEED_LITE_MODEL = "doubao-seed-2-0-lite-260215"


def resolve_chat_base_url(settings: Settings) -> str:
    if settings.llm_api_base_url and settings.llm_api_base_url.strip():
        return settings.llm_api_base_url.rstrip("/")
    if settings.video_api_base_url and settings.video_api_base_url.strip():
        return settings.video_api_base_url.rstrip("/")
    return DEFAULT_ARK_CHAT_BASE


def resolve_chat_api_key(settings: Settings) -> str:
    api_key = (settings.llm_api_key or settings.ark_api_key or "").strip()
    if not api_key:
        raise ArkApiError(
            "LLM_API_KEY or ARK_API_KEY is required for chat completions",
        )
    return api_key


def resolve_chat_model(settings: Settings) -> str:
    if settings.ark_chat_endpoint_id and settings.ark_chat_endpoint_id.strip():
        return settings.ark_chat_endpoint_id.strip()
    return (settings.llm_model or DEFAULT_DOUBAO_SEED_LITE_MODEL).strip()


def resolve_vision_model(settings: Settings) -> str:
    if settings.ark_chat_endpoint_id and settings.ark_chat_endpoint_id.strip():
        return settings.ark_chat_endpoint_id.strip()
    return (settings.vision_model or settings.llm_model or DEFAULT_DOUBAO_SEED_LITE_MODEL).strip()
