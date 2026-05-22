from __future__ import annotations

import httpx

from app.agent.schemas import SearchResult
from app.core.config import Settings
from app.providers.ark_client import ArkApiError, build_headers, request_json
from app.providers.volc_search import _parse_web_search_response


class FeedCoopSearchProvider:
    """
    FeedCoop-compatible web search endpoint.
    Uses the same Volcengine response envelope; Bearer auth when configured.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        api_key = settings.search_api_key or settings.ark_api_key
        if not settings.search_api_base_url:
            raise ArkApiError("SEARCH_API_BASE_URL is not configured")
        if not api_key:
            raise ArkApiError("SEARCH_API_KEY or ARK_API_KEY is required for FeedCoop search")

        self._settings = settings
        self._api_key = api_key
        self._client = client
        self._auth_scheme = settings.search_api_auth_scheme or "Bearer"

    async def search(self, query: str) -> SearchResult:
        payload = {
            "Query": query,
            "SearchType": "web",
            "Count": self._settings.search_result_count,
            "NeedSummary": True,
        }
        headers = build_headers(self._api_key)
        if self._auth_scheme.lower() != "bearer":
            headers["Authorization"] = f"{self._auth_scheme} {self._api_key}"

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        try:
            response = await request_json(
                client,
                self._settings.search_api_method.upper(),
                self._settings.search_api_base_url,
                api_key=self._api_key,
                json_body=payload,
            )
            return _parse_web_search_response(query, response)
        finally:
            if owns_client:
                await client.aclose()
