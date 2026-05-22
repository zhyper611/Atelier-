from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from redis.asyncio import Redis
from redisvl.index import AsyncSearchIndex
from redisvl.query import VectorQuery
from redisvl.query.filter import Tag

from app.agent.tools.document_parser import extract_text_from_bytes
from app.core.config import Settings
from app.knowledge.chunking import chunk_text
from app.knowledge.embeddings import EmbeddingProvider, build_embedding_provider
from app.knowledge.models import IndexDocumentResponse, KnowledgeCitation, KnowledgeDocument
from app.knowledge.schema import build_index_schema
from app.storage.attachments import AttachmentStore

logger = logging.getLogger(__name__)


def _parse_index_vector_dim(info: list[Any]) -> int | None:
    """Parse vector dimension from FT.INFO attributes list."""
    data: dict[Any, Any] = {}
    for i in range(0, len(info) - 1, 2):
        key = info[i]
        data[key if isinstance(key, str) else key.decode() if isinstance(key, bytes) else key] = (
            info[i + 1]
        )
    attrs = data.get("attributes") or data.get(b"attributes")
    if not attrs:
        return None
    for attr in attrs:
        items = list(attr)
        for j, item in enumerate(items):
            label = item.decode() if isinstance(item, bytes) else item
            if label == "dim" and j + 1 < len(items):
                dim_val = items[j + 1]
                return int(dim_val)
    return None


def _flatten_search_row(row: dict[str, Any]) -> dict[str, Any]:
    """Merge Redis JSON nested payload into top-level fields for citations."""
    merged = dict(row)
    nested = merged.get("json")
    if isinstance(nested, str):
        import json

        nested = json.loads(nested)
    if isinstance(nested, dict):
        merged.update(nested)
    return merged


def _doc_meta_key(user_id: str, doc_id: str) -> str:
    return f"kb:doc:{user_id}:{doc_id}"


def _user_docs_set_key(user_id: str) -> str:
    return f"kb:docs:{user_id}"


def _chunk_record_id(user_id: str, doc_id: str, chunk_index: int) -> str:
    return f"{user_id}:{doc_id}:{chunk_index}"


class KnowledgeStore:
    def __init__(
        self,
        redis_client: Redis,
        settings: Settings,
        *,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._redis = redis_client
        self._settings = settings
        self._embeddings = embedding_provider or build_embedding_provider(settings)
        schema = build_index_schema(settings)
        self._index = AsyncSearchIndex.from_dict(
            schema,
            redis_client=redis_client,
            validate_on_load=True,
        )
        self._ready = False

    @property
    def enabled(self) -> bool:
        return self._settings.knowledge_enabled

    async def _read_index_vector_dim(self) -> int | None:
        try:
            info = await self._redis.execute_command("FT.INFO", self._settings.knowledge_index_name)
            if isinstance(info, list):
                return _parse_index_vector_dim(info)
        except Exception as exc:
            logger.debug("read_index_vector_dim_failed", extra={"error": str(exc)})
        return None

    async def _rebuild_index_if_dim_mismatch(self) -> bool:
        """Drop and recreate the search index when embedding dims changed (keep chunk JSON)."""
        if not await self._index.exists():
            return False
        index_dim = await self._read_index_vector_dim()
        expected = self._settings.embedding_dimensions
        if index_dim is None or index_dim == expected:
            return False
        logger.warning(
            "knowledge_index_dim_mismatch_rebuild",
            extra={"index_dim": index_dim, "expected_dim": expected},
        )
        await self._index.delete(drop=False)
        await self._index.create(overwrite=False)
        return True

    async def ensure_index(self) -> None:
        if self._ready:
            return
        exists = await self._index.exists()
        if exists:
            await self._rebuild_index_if_dim_mismatch()
            exists = await self._index.exists()
        if not exists:
            await self._index.create(overwrite=False)
        self._ready = True

    async def ping(self) -> bool:
        try:
            await self._redis.ping()
            await self.ensure_index()
            return True
        except Exception:
            return False

    async def index_bytes(
        self,
        user_id: str,
        filename: str,
        data: bytes,
        mime: str,
        *,
        size_bytes: int | None = None,
    ) -> IndexDocumentResponse:
        await self.ensure_index()
        text = extract_text_from_bytes(data, mime, filename)
        chunks = chunk_text(
            text,
            chunk_size=self._settings.knowledge_chunk_size,
            overlap=self._settings.knowledge_chunk_overlap,
        )
        if not chunks:
            raise ValueError("文档分块后为空")

        doc_id = str(uuid4())
        vectors = await self._embeddings.embed_texts(chunks)
        records = []
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            records.append(
                {
                    "id": _chunk_record_id(user_id, doc_id, i),
                    "user_id": user_id,
                    "doc_id": doc_id,
                    "filename": filename,
                    "chunk_index": i,
                    "text": chunk,
                    "embedding": vector,
                }
            )

        await self._index.load(records, id_field="id")

        created_at = datetime.now(timezone.utc).isoformat()
        meta_key = _doc_meta_key(user_id, doc_id)
        await self._redis.hset(
            meta_key,
            mapping={
                "filename": filename,
                "size_bytes": str(size_bytes or len(data)),
                "chunk_count": str(len(chunks)),
                "created_at": created_at,
            },
        )
        await self._redis.sadd(_user_docs_set_key(user_id), doc_id)

        return IndexDocumentResponse(
            doc_id=doc_id,
            filename=filename,
            chunk_count=len(chunks),
        )

    async def index_from_attachment(
        self,
        attachment_store: AttachmentStore,
        user_id: str,
        session_id: str,
        attachment_id: str,
    ) -> IndexDocumentResponse:
        ref, data = attachment_store.read_bytes(user_id, session_id, attachment_id)
        return await self.index_bytes(
            user_id,
            ref.filename,
            data,
            ref.mime_type,
            size_bytes=ref.size_bytes,
        )

    async def list_documents(self, user_id: str) -> list[KnowledgeDocument]:
        doc_ids = await self._redis.smembers(_user_docs_set_key(user_id))
        documents: list[KnowledgeDocument] = []
        for raw_id in sorted(doc_ids):
            doc_id = raw_id if isinstance(raw_id, str) else raw_id.decode()
            meta = await self._redis.hgetall(_doc_meta_key(user_id, doc_id))
            if not meta:
                continue
            decoded = {
                (k if isinstance(k, str) else k.decode()): (
                    v if isinstance(v, str) else v.decode()
                )
                for k, v in meta.items()
            }
            documents.append(
                KnowledgeDocument(
                    doc_id=doc_id,
                    filename=decoded.get("filename", doc_id),
                    size_bytes=int(decoded.get("size_bytes", "0")),
                    chunk_count=int(decoded.get("chunk_count", "0")),
                    created_at=decoded.get("created_at", ""),
                )
            )
        documents.sort(key=lambda d: d.created_at, reverse=True)
        return documents

    async def delete_document(self, user_id: str, doc_id: str) -> bool:
        meta = await self._redis.hgetall(_doc_meta_key(user_id, doc_id))
        if not meta:
            return False
        decoded = {
            (k if isinstance(k, str) else k.decode()): (
                v if isinstance(v, str) else v.decode()
            )
            for k, v in meta.items()
        }
        chunk_count = int(decoded.get("chunk_count", "0"))
        ids = [_chunk_record_id(user_id, doc_id, i) for i in range(chunk_count)]
        if ids:
            await self._index.drop_documents(ids)
        await self._redis.delete(_doc_meta_key(user_id, doc_id))
        await self._redis.srem(_user_docs_set_key(user_id), doc_id)
        return True

    def _citations_from_results(
        self,
        user_id: str,
        results: list[dict[str, Any]],
    ) -> list[KnowledgeCitation]:
        citations: list[KnowledgeCitation] = []
        max_len = self._settings.knowledge_excerpt_max_chars
        for row in results:
            fields = _flatten_search_row(row)
            if str(fields.get("user_id") or "") != user_id:
                continue
            excerpt = str(fields.get("text") or "")
            if len(excerpt) > max_len:
                excerpt = excerpt[: max_len - 3] + "..."
            score_raw = fields.get("vector_distance")
            score = float(score_raw) if score_raw is not None else None
            citations.append(
                KnowledgeCitation(
                    index=len(citations) + 1,
                    doc_id=str(fields.get("doc_id") or ""),
                    filename=str(fields.get("filename") or ""),
                    chunk_index=int(fields.get("chunk_index") or 0),
                    excerpt=excerpt,
                    score=score,
                )
            )
        return citations

    async def _run_vector_query(
        self,
        user_id: str,
        vector: list[float],
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        tag_filter = Tag("user_id") == user_id
        vq = VectorQuery(
            vector=vector,
            vector_field_name="embedding",
            return_fields=[
                "user_id",
                "doc_id",
                "filename",
                "chunk_index",
                "text",
                "vector_distance",
            ],
            num_results=top_k,
            filter_expression=tag_filter,
            hybrid_policy="ADHOC_BF",
        )
        return await self._index.query(vq)

    async def search(
        self,
        user_id: str,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[KnowledgeCitation]:
        await self.ensure_index()
        query = query.strip()
        if not query:
            return []

        vector = await self._embeddings.embed_query(query)
        results = await self._run_vector_query(user_id, vector, top_k=top_k)
        citations = self._citations_from_results(user_id, results)

        if not citations and await self.list_documents(user_id):
            if await self._rebuild_index_if_dim_mismatch():
                results = await self._run_vector_query(user_id, vector, top_k=top_k)
                citations = self._citations_from_results(user_id, results)

        return citations

    async def delete_all_for_user(self, user_id: str) -> int:
        docs = await self.list_documents(user_id)
        count = 0
        for doc in docs:
            if await self.delete_document(user_id, doc.doc_id):
                count += 1
        return count
