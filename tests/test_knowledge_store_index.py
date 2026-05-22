from app.knowledge.store import _flatten_search_row, _parse_index_vector_dim


def test_parse_index_vector_dim_from_ft_info() -> None:
    info = [
        b"index_name",
        b"agent_kb",
        b"attributes",
        [
            [
                b"identifier",
                b"$.embedding",
                b"attribute",
                b"embedding",
                b"type",
                b"VECTOR",
                b"dim",
                2048,
                b"distance_metric",
                b"COSINE",
            ],
        ],
    ]
    assert _parse_index_vector_dim(info) == 2048


def test_flatten_search_row_merges_json_payload() -> None:
    row = {
        "id": "kb_chunk:u:d:0",
        "json": {
            "user_id": "u1",
            "doc_id": "d1",
            "filename": "a.pdf",
            "chunk_index": 0,
            "text": "hello",
        },
        "vector_distance": "0.12",
    }
    flat = _flatten_search_row(row)
    assert flat["text"] == "hello"
    assert flat["user_id"] == "u1"
