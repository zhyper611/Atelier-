from __future__ import annotations

import base64


def build_data_url(mime_type: str, data: bytes) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def attachment_to_content_part(mime_type: str, data_url: str) -> dict:
    if mime_type.startswith("image/"):
        return {"type": "image_url", "image_url": {"url": data_url}}
    if mime_type.startswith("video/"):
        return {"type": "video_url", "video_url": {"url": data_url}}
    if mime_type.startswith("audio/"):
        fmt = mime_type.split("/", 1)[-1] if "/" in mime_type else "mp3"
        if fmt == "mpeg":
            fmt = "mp3"
        if fmt == "x-wav":
            fmt = "wav"
        b64 = data_url.split(",", 1)[-1] if "," in data_url else data_url
        return {
            "type": "input_audio",
            "input_audio": {"data": b64, "format": fmt},
        }
    raise ValueError(f"Unsupported inline mime type: {mime_type}")
