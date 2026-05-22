from app.knowledge.chunking import chunk_text


def test_chunk_text_splits_with_overlap() -> None:
    text = "a" * 2000
    chunks = chunk_text(text, chunk_size=800, overlap=150)
    assert len(chunks) >= 2
    assert all(len(c) <= 800 for c in chunks)


def test_chunk_text_empty() -> None:
    assert chunk_text("   ") == []
