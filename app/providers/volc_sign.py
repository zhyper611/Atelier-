from __future__ import annotations

import datetime
import hashlib
import hmac
import json
from typing import Any, Literal
from urllib.parse import quote, urlparse, parse_qs

import httpx

from app.providers.ark_client import ArkApiError


def _hmac_sha256(key: bytes, content: str) -> bytes:
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()


def _hash_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _norm_query(params: dict[str, Any]) -> str:
    query = ""
    for key in sorted(params.keys()):
        value = params[key]
        if isinstance(value, list):
            for item in value:
                query += f"{quote(key, safe='-_.~')}={quote(str(item), safe='-_.~')}&"
        else:
            query += f"{quote(key, safe='-_.~')}={quote(str(value), safe='-_.~')}&"
    return query[:-1].replace("+", "%20")


def parse_mercury_endpoint(aksk_url: str | None) -> tuple[str, str, str]:
    if not aksk_url:
        return "mercury.volcengineapi.com", "WebSearch", "2025-01-01"

    parsed = urlparse(aksk_url)
    host = parsed.netloc or "mercury.volcengineapi.com"
    query = parse_qs(parsed.query)
    action = query.get("Action", ["WebSearch"])[0]
    version = query.get("Version", ["2025-01-01"])[0]
    return host, action, version


async def volc_signed_request(
    *,
    request_body: dict[str, Any],
    action: str,
    access_key_id: str,
    secret_access_key: str,
    service: str = "volc_torchlight_api",
    version: str = "2025-01-01",
    region: str = "cn-beijing",
    host: str = "mercury.volcengineapi.com",
    method: Literal["GET", "POST", "PUT", "DELETE"] = "POST",
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    body = json.dumps(request_body, ensure_ascii=False, separators=(",", ":"))
    now = datetime.datetime.now(datetime.UTC)
    x_date = now.strftime("%Y%m%dT%H%M%SZ")
    short_x_date = x_date[:8]
    x_content_sha256 = _hash_sha256(body)
    query = {"Action": action, "Version": version}
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_request = "\n".join(
        [
            method.upper(),
            "/",
            _norm_query(query),
            "\n".join(
                [
                    "content-type:application/json",
                    f"host:{host}",
                    f"x-content-sha256:{x_content_sha256}",
                    f"x-date:{x_date}",
                ]
            ),
            "",
            signed_headers,
            x_content_sha256,
        ]
    )
    credential_scope = "/".join([short_x_date, region, service, "request"])
    string_to_sign = "\n".join(
        ["HMAC-SHA256", x_date, credential_scope, _hash_sha256(canonical_request)]
    )
    k_date = _hmac_sha256(secret_access_key.encode("utf-8"), short_x_date)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    k_signing = _hmac_sha256(k_service, "request")
    signature = _hmac_sha256(k_signing, string_to_sign).hex()
    authorization = (
        f"HMAC-SHA256 Credential={access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    headers = {
        "Host": host,
        "X-Content-Sha256": x_content_sha256,
        "X-Date": x_date,
        "Content-Type": "application/json",
        "Authorization": authorization,
    }

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=httpx.Timeout(60.0))
    try:
        response = await http.request(
            method,
            f"https://{host}/",
            params=query,
            headers=headers,
            content=body.encode("utf-8"),
        )
    finally:
        if owns_client:
            await http.aclose()

    try:
        payload = response.json()
    except ValueError as exc:
        raise ArkApiError(
            f"Invalid JSON from Volcengine search API ({response.status_code})",
            status_code=response.status_code,
        ) from exc

    if response.status_code >= 400:
        raise ArkApiError(
            _extract_volc_error(payload) or response.text,
            status_code=response.status_code,
            payload=payload,
        )

    if not isinstance(payload, dict):
        raise ArkApiError("Unexpected Volcengine search response format")

    metadata = payload.get("ResponseMetadata")
    if isinstance(metadata, dict):
        error = metadata.get("Error")
        if isinstance(error, dict) and error.get("Message"):
            raise ArkApiError(str(error["Message"]), payload=payload)

    return payload


def _extract_volc_error(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    metadata = payload.get("ResponseMetadata")
    if isinstance(metadata, dict):
        error = metadata.get("Error")
        if isinstance(error, dict):
            message = error.get("Message")
            if isinstance(message, str):
                return message
    return None
