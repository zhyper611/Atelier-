from __future__ import annotations

import httpx

from app.agent.schemas import SearchResult
from app.core.config import Settings
from app.providers.ark_client import ArkApiError
from app.providers.volc_sign import parse_mercury_endpoint, volc_signed_request


class VolcMercurySearchProvider:
    """Volcengine fusion web search via mercury.volcengineapi.com (AK/SK)."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if not settings.volc_access_key_id or not settings.volc_secret_access_key:
            raise ArkApiError("VOLC_ACCESS_KEY_ID and VOLC_SECRET_ACCESS_KEY are required for web search")

        self._settings = settings
        self._client = client
        self._host, self._action, self._version = parse_mercury_endpoint(settings.search_api_aksk_url)

    async def search(self, query: str) -> SearchResult:
        response = await volc_signed_request(
            request_body={
                "Query": query,
                "SearchType": "web",
                "Count": self._settings.search_result_count,
                "NeedSummary": True,
            },
            action=self._action,
            access_key_id=self._settings.volc_access_key_id,
            secret_access_key=self._settings.volc_secret_access_key,
            version=self._version,
            region=self._settings.volc_region,
            host=self._host,
            client=self._client,
        )
        return _parse_web_search_response(query, response)


def _parse_web_search_response(query: str, payload: dict) -> SearchResult:
    metadata = payload.get("ResponseMetadata")
    if isinstance(metadata, dict):
        error = metadata.get("Error")
        if isinstance(error, dict) and error.get("Message"):
            raise ArkApiError(str(error["Message"]), payload=payload)

    result = payload.get("Result")
    if not isinstance(result, dict):
        raise ArkApiError("Volcengine search response missing Result", payload=payload)

    web_results = result.get("WebResults")
    if not isinstance(web_results, list) or not web_results:
        raise ArkApiError("Volcengine search returned no web results", payload=payload)

    summaries: list[str] = []
    sources: list[str] = []

    for index, item in enumerate(web_results, start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("Title") or item.get("title") or f"结果 {index}").strip()
        summary = str(item.get("Summary") or item.get("summary") or item.get("Snippet") or "").strip()
        url = str(item.get("Url") or item.get("url") or item.get("Link") or "").strip()

        if summary:
            summaries.append(f"{index}. {title}\n{summary}")
        else:
            summaries.append(f"{index}. {title}")

        if url:
            sources.append(url)

    combined_summary = "\n\n".join(summaries) if summaries else "未获取到可用摘要。"
    return SearchResult(query=query, summary=combined_summary, sources=sources)
