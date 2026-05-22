from __future__ import annotations


def chunk_text(
    text: str,
    *,
    chunk_size: int = 800,
    overlap: int = 150,
) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    overlap = min(overlap, max(0, chunk_size - 1))
    step = chunk_size - overlap
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start += step
    return chunks
