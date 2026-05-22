from __future__ import annotations

import io

from pypdf import PdfReader

from app.storage.attachments import AttachmentStore


def extract_text_from_bytes(
    data: bytes,
    mime: str,
    filename: str,
    *,
    max_chars: int = 12000,
) -> str:
    if mime == "application/pdf" or filename.lower().endswith(".pdf"):
        text = _extract_pdf(data)
    elif mime in {"text/plain", "text/markdown"} or filename.lower().endswith(
        (".txt", ".md")
    ):
        text = data.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported document type: {mime}")

    text = text.strip()
    if not text:
        raise ValueError("No text extracted from document")
    if len(text) > max_chars:
        text = text[: max_chars - 3] + "..."
    return text


def parse_attachment_text(
    store: AttachmentStore,
    user_id: str,
    session_id: str,
    attachment_id: str,
    *,
    max_chars: int = 12000,
) -> tuple[str, str]:
    ref, data = store.read_bytes(user_id, session_id, attachment_id)
    text = extract_text_from_bytes(
        data,
        ref.mime_type,
        ref.filename,
        max_chars=max_chars,
    )
    return ref.filename, text


def _extract_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            parts.append(page_text)
    return "\n\n".join(parts)
