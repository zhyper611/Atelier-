from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.agent.schemas import AttachmentRef
from app.core.config import Settings

_ALLOWED_MIME_PREFIXES = ("image/", "audio/", "video/")
_ALLOWED_MIME_EXACT = {
    "application/pdf",
    "text/plain",
    "text/markdown",
}
_SAFE_FILENAME = re.compile(r"^[\w.\- ]+$", re.UNICODE)


def _is_allowed_mime(mime_type: str) -> bool:
    if mime_type in _ALLOWED_MIME_EXACT:
        return True
    return any(mime_type.startswith(prefix) for prefix in _ALLOWED_MIME_PREFIXES)


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    if not name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not _SAFE_FILENAME.match(name):
        safe = re.sub(r"[^\w.\- ]", "_", name)
        if not safe:
            raise HTTPException(status_code=400, detail="Invalid filename")
        return safe
    return name


class AttachmentStore:
    def __init__(self, settings: Settings) -> None:
        self._root = Path(settings.attachments_dir)
        self._max_bytes = settings.attachment_max_bytes
        self._root.mkdir(parents=True, exist_ok=True)

    def _validate_segment(self, value: str, *, field_name: str) -> str:
        if not value or ".." in value or "/" in value or "\\" in value:
            raise HTTPException(status_code=400, detail=f"Invalid {field_name}")
        return value

    def _session_dir(self, user_id: str, session_id: str) -> Path:
        safe_user = self._validate_segment(user_id, field_name="user_id")
        safe_session = self._validate_segment(session_id, field_name="session_id")
        path = self._root / safe_user / safe_session
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _resolve_path(self, user_id: str, session_id: str, attachment_id: str) -> Path:
        if not attachment_id or ".." in attachment_id:
            raise HTTPException(status_code=400, detail="Invalid attachment_id")
        session_dir = self._session_dir(user_id, session_id)
        matches = list(session_dir.glob(f"{attachment_id}_*"))
        if not matches:
            raise HTTPException(status_code=404, detail="Attachment not found")
        return matches[0]

    async def save_upload(
        self,
        user_id: str,
        session_id: str,
        upload: UploadFile,
    ) -> AttachmentRef:
        mime_type = (upload.content_type or "application/octet-stream").split(";")[0].strip()
        if not _is_allowed_mime(mime_type):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {mime_type}",
            )

        filename = _sanitize_filename(upload.filename or "file")
        data = await upload.read()
        if len(data) > self._max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds max size ({self._max_bytes} bytes)",
            )
        if not data:
            raise HTTPException(status_code=400, detail="Empty file")

        attachment_id = str(uuid4())
        dest = self._session_dir(user_id, session_id) / f"{attachment_id}_{filename}"
        dest.write_bytes(data)

        return AttachmentRef(
            id=attachment_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
        )

    def get_ref(self, user_id: str, session_id: str, attachment_id: str) -> AttachmentRef:
        path = self._resolve_path(user_id, session_id, attachment_id)
        name = path.name
        rest = name.split("_", 1)
        filename = rest[1] if len(rest) > 1 else name
        mime_type = _guess_mime(filename)
        return AttachmentRef(
            id=attachment_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=path.stat().st_size,
        )

    def read_bytes(
        self,
        user_id: str,
        session_id: str,
        attachment_id: str,
    ) -> tuple[AttachmentRef, bytes]:
        ref = self.get_ref(user_id, session_id, attachment_id)
        path = self._resolve_path(user_id, session_id, attachment_id)
        return ref, path.read_bytes()

    def delete(self, user_id: str, session_id: str, attachment_id: str) -> bool:
        try:
            path = self._resolve_path(user_id, session_id, attachment_id)
        except HTTPException:
            return False
        path.unlink(missing_ok=True)
        return True


def _guess_mime(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".md"):
        return "text/markdown"
    if lower.endswith(".txt"):
        return "text/plain"
    if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        ext = lower.rsplit(".", 1)[-1]
        if ext == "jpg":
            ext = "jpeg"
        return f"image/{ext}"
    return "application/octet-stream"
