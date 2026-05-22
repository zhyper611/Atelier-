from app.agent.tools.document_parser import extract_text_from_bytes


def test_extract_text_from_plain_bytes() -> None:
    text = extract_text_from_bytes(
        b"hello knowledge",
        "text/plain",
        "notes.txt",
    )
    assert "hello knowledge" in text
