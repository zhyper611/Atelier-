from __future__ import annotations

import asyncio
import hashlib
import struct
from typing import Protocol

import httpx
import numpy as np

from app.core.config import Settings


class EmbeddingProvider(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


def _is_volc_multimodal_embedding_model(model: str) -> bool:
    return model.startswith("doubao-embedding-vision")


class MockEmbeddingProvider:
    def __init__(self, dimensions: int = 2048) -> None:
        self.dimensions = dimensions

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        while len(values) < self.dimensions:
            for i in range(0, len(digest) - 3, 4):
                raw = struct.unpack(">i", digest[i : i + 4])[0]
                values.append((raw % 1000) / 1000.0 - 0.5)
                if len(values) >= self.dimensions:
                    break
            digest = hashlib.sha256(digest).digest()
        arr = np.array(values[: self.dimensions], dtype=np.float32)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr.tolist()


class OpenAIEmbeddingProvider:
    """OpenAI 兼容 /embeddings（非 doubao-embedding-vision）。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.timeout_seconds = timeout_seconds

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload: dict = {"model": self.model, "input": texts}
        if self.dimensions and not self.model.startswith("doubao-embedding"):
            payload["dimensions"] = self.dimensions
        data = await self._post("/embeddings", payload)
        items = sorted(data["data"], key=lambda x: x["index"])
        vectors = [item["embedding"] for item in items]
        _validate_dimensions(vectors, self.dimensions, self.model)
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]

    async def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        return await _request_json(
            url,
            api_key=self.api_key,
            payload=payload,
            timeout_seconds=self.timeout_seconds,
        )


class VolcengineMultimodalEmbeddingProvider:
    """火山方舟 doubao-embedding-vision：/embeddings/multimodal，纯文本用 type=text。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int,
        timeout_seconds: float = 60.0,
        max_concurrency: int = 8,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.timeout_seconds = timeout_seconds
        self.max_concurrency = max_concurrency

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _one(text: str) -> list[float]:
            async with semaphore:
                return await self._embed_single(text)

        vectors = await asyncio.gather(*[_one(text) for text in texts])
        _validate_dimensions(list(vectors), self.dimensions, self.model)
        return list(vectors)

    async def embed_query(self, text: str) -> list[float]:
        return await self._embed_single(text)

    async def _embed_single(self, text: str) -> list[float]:
        payload = {
            "model": self.model,
            "input": [{"type": "text", "text": text}],
        }
        data = await self._post(payload)
        block = data.get("data")
        if isinstance(block, dict) and "embedding" in block:
            return block["embedding"]
        if isinstance(block, list) and block:
            first = block[0]
            if isinstance(first, dict) and "embedding" in first:
                return first["embedding"]
        raise ValueError(f"Unexpected multimodal embedding response: {data!r}")

    async def _post(self, payload: dict) -> dict:
        return await _request_json(
            f"{self.base_url}/embeddings/multimodal",
            api_key=self.api_key,
            payload=payload,
            timeout_seconds=self.timeout_seconds,
        )


def _validate_dimensions(
    vectors: list[list[float]],
    expected: int,
    model: str,
) -> None:
    for vector in vectors:
        if len(vector) != expected:
            raise ValueError(
                f"Embedding dimension mismatch: expected {expected}, "
                f"got {len(vector)} for model {model}. "
                f"请检查 .env 中 EMBEDDING_DIMENSIONS 是否与模型一致（"
                f"doubao-embedding-vision-251215 当前接口返回 2048 维）。"
            )


async def _request_json(
    url: str,
    *,
    api_key: str,
    payload: dict,
    timeout_seconds: float,
) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code >= 400:
            detail = response.text
            try:
                body = response.json()
                err = body.get("error") if isinstance(body, dict) else None
                if isinstance(err, dict) and err.get("message"):
                    detail = str(err["message"])
            except Exception:
                pass
            raise RuntimeError(
                f"Embedding API error ({response.status_code}): {detail}",
            ) from None
        return response.json()


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.use_mock_providers:
        return MockEmbeddingProvider(settings.embedding_dimensions)
    base_url = settings.resolved_embedding_api_base_url()
    api_key = settings.resolved_embedding_api_key()
    if not base_url or not api_key:
        return MockEmbeddingProvider(settings.embedding_dimensions)
    if _is_volc_multimodal_embedding_model(settings.embedding_model):
        return VolcengineMultimodalEmbeddingProvider(
            base_url=base_url,
            api_key=api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    return OpenAIEmbeddingProvider(
        base_url=base_url,
        api_key=api_key,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
    )
