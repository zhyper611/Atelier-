from __future__ import annotations

import httpx

from app.core.config import Settings


class ArkApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, payload: object = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def resolve_api_key(settings: Settings, *, preferred: str | None = None) -> str:
    api_key = preferred or settings.image_api_key or settings.video_api_key or settings.ark_api_key
    if not api_key:
        raise ArkApiError("ARK API key is not configured")
    return api_key


def build_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    api_key: str,
    json_body: dict | None = None,
) -> dict:
    response = await client.request(
        method,
        url,
        headers=build_headers(api_key),
        json=json_body,
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise ArkApiError(
            f"Invalid JSON response from Ark API ({response.status_code})",
            status_code=response.status_code,
        ) from exc

    if response.status_code >= 400:
        message = _extract_error_message(payload) or response.text or "Ark API request failed"
        raise ArkApiError(message, status_code=response.status_code, payload=payload)

    if not isinstance(payload, dict):
        raise ArkApiError("Unexpected Ark API response format", status_code=response.status_code)
    return payload


def humanize_provider_error(exc: BaseException) -> str:
    """Map provider errors to user-facing Chinese messages."""
    message = str(exc).strip()
    lowered = message.lower()

    if "sensitive information" in lowered or "敏感" in message:
        return (
            "生成请求未通过平台内容安全审核，请调整描述后重试。"
            "可尝试更通用、中性的表述（例如「城市广场」「标志性建筑航拍」），"
            "避免涉及受限的地标或政治敏感内容。"
        )

    if "rate limit" in lowered or "too many requests" in lowered:
        return "请求过于频繁，请稍后再试。"

    if "not activated" in lowered or "activate the model" in lowered:
        return (
            "当前账号未开通 .env 里配置的对话模型。"
            "请登录火山方舟控制台 → 在线推理 → 创建推理接入点（选择已开通的 Doubao-Seed-2.0-lite "
            "或其它多模态模型），将接入点 ID（形如 ep-xxxx）填入 ARK_CHAT_ENDPOINT_ID 或 LLM_MODEL 后重启服务。"
        )

    if "timeout" in lowered or "timed out" in lowered:
        return "服务响应超时，请稍后重试。"

    if isinstance(exc, httpx.ConnectError):
        return (
            "无法连接大模型服务（ConnectError）。请检查本机网络、代理/VPN，"
            "以及 .env 中 LLM_API_BASE_URL 是否可访问（如火山方舟 ark.cn-beijing.volces.com）。"
        )

    if "llm stream" in lowered or "llm api" in lowered:
        return (
            "大模型流式接口调用失败，请检查 LLM 服务是否可用、"
            f"以及 .env 中 LLM_MODEL / LLM_API_BASE_URL 配置。详情：{message}"
        )

    if message:
        return f"处理失败：{message}"

    if isinstance(exc, ArkApiError):
        detail = _extract_error_message(exc.payload) if exc.payload else None
        if detail:
            return f"处理失败：{detail}"
        if exc.status_code:
            return f"处理失败：上游接口 HTTP {exc.status_code}，请查看后端日志。"

    name = type(exc).__name__
    return f"处理失败（{name}），请查看后端 uvicorn 日志或稍后重试。"


def _extract_error_message(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message
    message = payload.get("message")
    if isinstance(message, str):
        return message
    return None


def extract_image_url(payload: dict) -> str:
    data = payload.get("data")
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if isinstance(url, str) and url:
                return url
            b64_json = item.get("b64_json")
            if isinstance(b64_json, str) and b64_json:
                return f"data:image/png;base64,{b64_json}"

    output = payload.get("output")
    if isinstance(output, dict):
        url = output.get("url")
        if isinstance(url, str) and url:
            return url

    raise ArkApiError("Ark image API response did not include an image URL", payload=payload)


def extract_task_id(payload: dict) -> str:
    task_id = payload.get("id")
    if isinstance(task_id, str) and task_id:
        return task_id
    raise ArkApiError("Ark video API response did not include a task id", payload=payload)


def extract_video_url(payload: dict) -> str | None:
    content = payload.get("content")
    if isinstance(content, dict):
        for key in ("video_url", "url"):
            value = content.get(key)
            if isinstance(value, str) and value:
                return value

    for key in ("video_url", "url"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value

    output = payload.get("output")
    if isinstance(output, dict):
        for key in ("video_url", "url"):
            value = output.get(key)
            if isinstance(value, str) and value:
                return value

    return None


def extract_task_status(payload: dict) -> str:
    status = payload.get("status")
    if isinstance(status, str):
        return status.lower()
    return "unknown"


def is_terminal_status(status: str) -> bool:
    return status in {"succeeded", "completed", "failed", "expired", "cancelled"}


def is_success_status(status: str) -> bool:
    return status in {"succeeded", "completed"}
