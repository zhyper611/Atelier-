from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx
import trafilatura

from app.core.config import Settings


class UrlFetchError(Exception):
    """User-facing URL fetch failure."""


@dataclass(frozen=True)
class FetchPageResult:
    url: str
    title: str
    text: str
    char_count: int
    truncated: bool
    error: str | None = None


def _punycode_label(label: str) -> str:
    if not label:
        return label
    try:
        return label.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise UrlFetchError(f"域名标签无法编码：{label}") from exc


def normalize_url_for_fetch(url: str) -> str:
    """Encode IDN host to punycode so httpx can resolve and connect."""
    parsed = urlparse(url.strip())
    if not parsed.hostname:
        return url.strip()
    host = parsed.hostname
    if host.isascii():
        return url.strip()
    puny_host = ".".join(_punycode_label(part) for part in host.split("."))
    netloc = puny_host
    if parsed.port:
        netloc = f"{puny_host}:{parsed.port}"
    if parsed.username:
        auth = parsed.username
        if parsed.password:
            auth = f"{auth}:{parsed.password}"
        netloc = f"{auth}@{netloc}"
    rebuilt = urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path or "",
            parsed.params,
            parsed.query,
            parsed.fragment,
        ),
    )
    return rebuilt


def _default_fetch_headers(settings: Settings) -> dict[str, str]:
    return {
        "User-Agent": settings.fetch_url_user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def humanize_http_error(exc: BaseException) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "请求超时，请稍后重试或换用其他链接。"
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 404:
            return (
                "HTTP 404：页面不存在或链接已失效"
                "（常见于搜索返回的过期/虚构链接，请换用其他来源）。"
            )
        if code == 403:
            return "HTTP 403：站点拒绝访问（可能需登录或反爬）。"
        if code >= 500:
            return f"HTTP {code}：目标服务器错误，请稍后重试。"
        return f"HTTP {code}：无法获取页面。"
    if isinstance(exc, httpx.ConnectError):
        return "无法连接目标站点（域名无法解析、网络不通或站点已下线）。"
    if isinstance(exc, httpx.HTTPError):
        detail = str(exc).strip()
        if detail:
            return f"网络请求失败：{detail}"
        return f"网络请求失败（{type(exc).__name__}）。"
    return str(exc)


def parse_blocked_domains(raw: str) -> frozenset[str]:
    domains: set[str] = set()
    for part in raw.split(","):
        token = part.strip().lower()
        if token:
            domains.add(token)
    return frozenset(domains)


def validate_url(url: str, settings: Settings) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise UrlFetchError("仅支持 http 或 https 链接。")

    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise UrlFetchError("URL 缺少有效主机名。")

    blocked = parse_blocked_domains(settings.fetch_url_blocked_domains)
    for blocked_host in blocked:
        if host == blocked_host or host.endswith(f".{blocked_host}"):
            raise UrlFetchError(f"域名 {host} 在禁止访问列表中。")

    if host in {"localhost", "metadata", "metadata.google", "metadata.google.internal"}:
        raise UrlFetchError(f"不允许访问主机：{host}")

    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return normalize_url_for_fetch(url.strip())

    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
    ):
        raise UrlFetchError("不允许访问内网或保留地址。")

    return normalize_url_for_fetch(url.strip())


def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[: max_chars - 3] + "...", True


def _extract_html(html: str, url: str) -> tuple[str, str]:
    text = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )
    title = ""
    if text:
        meta = trafilatura.extract_metadata(html, default_url=url)
        if meta and meta.title:
            title = meta.title.strip()
        return title, text.strip()

    bare = trafilatura.bare_extraction(html, url=url)
    if isinstance(bare, dict):
        title = str(bare.get("title") or "").strip()
        body = str(bare.get("text") or bare.get("raw_text") or "").strip()
        if body:
            return title, body

    return "", ""


def _decode_body(data: bytes, content_type: str | None) -> str:
    encoding = "utf-8"
    if content_type and "charset=" in content_type.lower():
        fragment = content_type.lower().split("charset=", 1)[-1].split(";")[0].strip()
        if fragment:
            encoding = fragment
    return data.decode(encoding, errors="replace")


async def _read_response_body(
    response: httpx.Response,
    max_bytes: int,
) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise UrlFetchError(f"响应体超过 {max_bytes} 字节上限。")
        chunks.append(chunk)
    return b"".join(chunks)


async def fetch_and_extract(
    url: str,
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> FetchPageResult:
    if not settings.fetch_url_enabled:
        raise UrlFetchError("网页抓取功能已关闭。")

    normalized = validate_url(url, settings)
    request_url = normalize_url_for_fetch(normalized)
    owns_client = client is None
    headers = _default_fetch_headers(settings)
    if owns_client:
        timeout = httpx.Timeout(settings.fetch_url_timeout_seconds)
        client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            max_redirects=settings.fetch_url_max_redirects,
            headers=headers,
        )

    try:
        response = await client.get(request_url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        body = await _read_response_body(response, settings.fetch_url_max_bytes)
        lowered = content_type.lower()

        if "text/html" in lowered or not content_type:
            html = _decode_body(body, content_type)
            title, text = _extract_html(html, request_url)
            if not text:
                return FetchPageResult(
                    url=normalized,
                    title=title,
                    text="未能从页面提取正文（可能需登录、反爬或页面为 JS 渲染）。",
                    char_count=0,
                    truncated=False,
                )
            text, truncated = _truncate_text(text, settings.fetch_url_max_content_chars)
            return FetchPageResult(
                url=normalized,
                title=title,
                text=text,
                char_count=len(text),
                truncated=truncated,
            )

        if "text/plain" in lowered:
            text = _decode_body(body, content_type).strip()
            text, truncated = _truncate_text(text, settings.fetch_url_max_content_chars)
            return FetchPageResult(
                url=normalized,
                title="",
                text=text or "页面无文本内容。",
                char_count=len(text),
                truncated=truncated,
            )

        return FetchPageResult(
            url=normalized,
            title="",
            text=f"不支持的内容类型：{content_type or 'unknown'}。",
            char_count=0,
            truncated=False,
        )
    except UrlFetchError:
        raise
    except httpx.HTTPError as exc:
        raise UrlFetchError(humanize_http_error(exc)) from exc
    finally:
        if owns_client and client is not None:
            await client.aclose()


def coerce_urls(urls_arg: Any, url_arg: Any) -> list[str]:
    collected: list[str] = []
    if isinstance(urls_arg, list):
        for item in urls_arg:
            if isinstance(item, str) and item.strip():
                collected.append(item.strip())
    elif isinstance(urls_arg, str) and urls_arg.strip():
        collected.append(urls_arg.strip())
    if isinstance(url_arg, str) and url_arg.strip():
        collected.append(url_arg.strip())

    seen: set[str] = set()
    unique: list[str] = []
    for url in collected:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


async def fetch_urls(urls: list[str], settings: Settings) -> list[FetchPageResult]:
    if not urls:
        raise UrlFetchError("fetch_url 缺少 urls 参数。")

    limited = urls[: settings.fetch_url_max_urls_per_call]
    if len(urls) > len(limited):
        pass  # silently cap; observation can note count

    timeout = httpx.Timeout(settings.fetch_url_timeout_seconds)
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        max_redirects=settings.fetch_url_max_redirects,
        headers=_default_fetch_headers(settings),
    ) as client:
        results: list[FetchPageResult] = []
        for url in limited:
            try:
                results.append(await fetch_and_extract(url, settings, client=client))
            except UrlFetchError as exc:
                results.append(
                    FetchPageResult(
                        url=url,
                        title="",
                        text="",
                        char_count=0,
                        truncated=False,
                        error=str(exc),
                    ),
                )
        return results


def format_fetch_observation(results: list[FetchPageResult]) -> str:
    parts: list[str] = []
    for index, item in enumerate(results, start=1):
        block = [f"[{index}] {item.url}"]
        if item.error:
            block.append(f"错误：{item.error}")
        else:
            if item.title:
                block.append(f"标题：{item.title}")
            block.append("正文：")
            block.append(item.text or "（无正文）")
            if item.truncated:
                block.append("（正文已截断）")
            block.append(f"字数：{item.char_count}")
        parts.append("\n".join(block))
    return "\n---\n".join(parts)


def results_to_metadata(results: list[FetchPageResult]) -> dict[str, Any]:
    return {
        "urls": [r.url for r in results],
        "results": [
            {
                "url": r.url,
                "title": r.title,
                "char_count": r.char_count,
                "truncated": r.truncated,
                "error": r.error,
            }
            for r in results
        ],
    }
