from __future__ import annotations

from app.core.config import Settings


def build_index_schema(settings: Settings) -> dict:
    dims = settings.embedding_dimensions
    return {
        "index": {
            "name": settings.knowledge_index_name,
            "prefix": "kb_chunk:",
            "storage_type": "json",
        },
        "fields": [
            {"name": "user_id", "type": "tag"},
            {"name": "doc_id", "type": "tag"},
            {"name": "filename", "type": "text"},
            {"name": "chunk_index", "type": "numeric"},
            {"name": "text", "type": "text"},
            {
                "name": "embedding",
                "type": "vector",
                "attrs": {
                    "dims": dims,
                    "distance_metric": "cosine",
                    "algorithm": "hnsw",
                    "datatype": "float32",
                },
            },
        ],
    }
