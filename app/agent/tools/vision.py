from __future__ import annotations

import base64

from app.providers.base import ChatProvider
from app.storage.attachments import AttachmentStore


def build_image_data_url(mime_type: str, data: bytes) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


async def analyze_session_image(
    chat_provider: ChatProvider,
    store: AttachmentStore,
    user_id: str,
    session_id: str,
    attachment_id: str,
    question: str | None = None,
) -> tuple[str, str]:
    ref, data = store.read_bytes(user_id, session_id, attachment_id)
    if not ref.mime_type.startswith("image/"):
        raise ValueError(f"Attachment is not an image: {ref.mime_type}")

    data_url = build_image_data_url(ref.mime_type, data)
    prompt = question.strip() if question and question.strip() else "请详细描述这张图片的内容。"
    description = await chat_provider.describe_image(prompt, data_url)
    return ref.filename, description.strip()
