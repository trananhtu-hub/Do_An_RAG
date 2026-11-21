from __future__ import annotations

import hashlib
import time
from collections.abc import Sequence
from typing import Protocol

import httpx

from .cache import TTLCache

EMBEDDING_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class QueryEmbeddingError(RuntimeError):
    pass


class QueryEmbedder(Protocol):
    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]: ...


def _cache_key(model: str, dimensions: int, task_type: str, text: str) -> str:
    payload = f"{model}|{dimensions}|{task_type}|{text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class GeminiQueryEmbedder:
    def __init__(
        self,
        api_key: str | Sequence[str],
        *,
        model: str = "gemini-embedding-001",
        dimensions: int = 768,
        task_type: str = "RETRIEVAL_QUERY",
        timeout_ms: int = 8000,
        max_retries: int = 2,
        cache_size: int = 512,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        keys = [part.strip() for part in str(api_key).split(",") if part.strip()]
        if not keys:
            raise ValueError("Thiếu GEMINI_API_KEY để sinh embedding truy vấn")
        self._keys = keys
        self._key_index = 0
        self.model = model
        self.dimensions = dimensions
        self.task_type = task_type
        self.max_retries = max_retries
        self._client = httpx.Client(timeout=timeout_ms / 1000.0, transport=transport)
        self._cache: TTLCache[list[float]] = TTLCache(3600, cache_size)

    def close(self) -> None:
        self._client.close()

    @property
    def url(self) -> str:
        return EMBEDDING_URL.format(model=self.model)

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        missing: list[str] = []
        results: dict[str, list[float]] = {}
        for text in texts:
            cached = self._cache.get(_cache_key(self.model, self.dimensions, self.task_type, text))
            if cached is None:
                if text not in missing:
                    missing.append(text)
            else:
                results[text] = cached
        if missing:
            vectors = self._request(missing)
            for text, vector in zip(missing, vectors, strict=True):
                results[text] = vector
                self._cache.set(
                    _cache_key(self.model, self.dimensions, self.task_type, text), vector
                )
        return [results[text] for text in texts]

    def _request(self, texts: list[str]) -> list[list[float]]:
        payload = {
            "requests": [
                {
                    "model": f"models/{self.model}",
                    "content": {"parts": [{"text": text}]},
                    "taskType": self.task_type,
                    "outputDimensionality": self.dimensions,
                }
                for text in texts
            ]
        }
        attempts = self.max_retries + 1
        last_error = "không rõ"
        for attempt in range(attempts):
            try:
                response = self._client.post(
                    self.url,
                    headers={
                        "x-goog-api-key": self._keys[self._key_index % len(self._keys)],
                        "content-type": "application/json",
                    },
                    json=payload,
                )
            except httpx.HTTPError as exc:
                last_error = f"lỗi mạng: {type(exc).__name__}"
            else:
                if response.status_code < 400:
                    return self._parse(response)
                last_error = f"HTTP {response.status_code}"
                if response.status_code in RETRYABLE_STATUS and attempt + 1 < attempts:
                    self._key_index += 1
                    time.sleep(0.4 * (attempt + 1))
                    continue
                detail = response.text[:200].replace("\n", " ")
                raise QueryEmbeddingError(f"Gemini trả mã {response.status_code}: {detail}")
            if attempt + 1 < attempts:
                time.sleep(0.4 * (attempt + 1))
        raise QueryEmbeddingError(
            f"Không sinh được embedding truy vấn sau {attempts} lần: {last_error}"
        )

    def _parse(self, response: httpx.Response) -> list[list[float]]:
        try:
            data = response.json()
        except ValueError as exc:
            raise QueryEmbeddingError("Phản hồi embedding không phải JSON hợp lệ") from exc
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or not embeddings:
            raise QueryEmbeddingError("Phản hồi embedding thiếu trường 'embeddings'")
        vectors: list[list[float]] = []
        for item in embeddings:
            values = item.get("values") if isinstance(item, dict) else None
            if not isinstance(values, list) or len(values) != self.dimensions:
                raise QueryEmbeddingError(f"Vector truy vấn không đúng {self.dimensions} chiều")
            vectors.append([float(value) for value in values])
        return vectors
