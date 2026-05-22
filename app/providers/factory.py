from __future__ import annotations

import os

from app.core.config import Settings
from app.providers.ark_image import ArkImageProvider
from app.providers.ark_video import ArkVideoProvider
from app.providers.base import ChatProvider, ImageProvider, SearchProvider, VideoProvider
from app.providers.mock import (
    MockChatProvider,
    MockImageProvider,
    MockSearchProvider,
    MockVideoProvider,
)
from app.providers.feedcoop_search import FeedCoopSearchProvider
from app.providers.openai_chat import OpenAIChatProvider
from app.providers.volc_search import VolcMercurySearchProvider


def _use_mock_providers(settings: Settings) -> bool:
    flag = os.getenv("USE_MOCK_PROVIDERS", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    return settings.use_mock_providers


def build_chat_provider(settings: Settings) -> ChatProvider:
    if _use_mock_providers(settings):
        return MockChatProvider()

    has_llm = bool(settings.llm_api_base_url or settings.video_api_base_url)
    has_key = bool(settings.llm_api_key or settings.ark_api_key)
    if has_llm and has_key:
        return OpenAIChatProvider(settings)

    return MockChatProvider()


def build_search_provider(settings: Settings) -> SearchProvider:
    if _use_mock_providers(settings):
        return MockSearchProvider()

    if settings.volc_access_key_id and settings.volc_secret_access_key:
        return VolcMercurySearchProvider(settings)

    api_key = settings.search_api_key or settings.ark_api_key
    if settings.search_api_base_url and api_key:
        return FeedCoopSearchProvider(settings)

    return MockSearchProvider()


def build_image_provider(settings: Settings) -> ImageProvider:
    if _use_mock_providers(settings):
        return MockImageProvider()

    api_key = settings.image_api_key or settings.ark_api_key
    if settings.image_api_base_url and api_key:
        return ArkImageProvider(settings)

    return MockImageProvider()


def build_video_provider(settings: Settings) -> VideoProvider:
    if _use_mock_providers(settings):
        return MockVideoProvider()

    api_key = settings.video_api_key or settings.ark_api_key
    if settings.video_tasks_url and settings.video_task_status_url_template and api_key:
        return ArkVideoProvider(settings)

    return MockVideoProvider()


