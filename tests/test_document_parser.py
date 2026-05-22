import pytest

from app.agent.tools.document_parser import parse_attachment_text
from app.core.config import get_settings
from app.storage.attachments import AttachmentStore


@pytest.mark.asyncio
async def test_parse_txt_attachment(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATTACHMENTS_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()
    store = AttachmentStore(settings)
    user_id = "test-user"
    session_id = "doc-session"

    class FakeUpload:
        filename = "notes.txt"
        content_type = "text/plain"

        async def read(self) -> bytes:
            return b"hello document"

    ref = await store.save_upload(user_id, session_id, FakeUpload())
    filename, text = parse_attachment_text(store, user_id, session_id, ref.id)
    assert filename == "notes.txt"
    assert "hello document" in text
    get_settings.cache_clear()
