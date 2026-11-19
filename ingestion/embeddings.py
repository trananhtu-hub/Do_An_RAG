from __future__ import annotations

import math
import random
import re
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass

import httpx

from .config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_CHARS_PER_TOKEN,
    EMBEDDING_DIM,
    EMBEDDING_MAX_INPUT_TOKENS,
    EMBEDDING_MAX_TOKENS_PER_REQUEST,
    EMBEDDING_MODEL,
    EMBEDDING_TASK_TYPE,
    EMBEDDING_TPM_LIMIT,
)

EMBEDDING_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/" "{model}:batchEmbedContents"
)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 8
BASE_DELAY_SECONDS = 2.0
MAX_RETRY_AFTER_SECONDS = 90.0
MAX_TOKENS_PER_REQUEST = 20_000
QUOTA_CONFIRM_DELAY_SECONDS = 5.0
RETRY_IN_PATTERN = re.compile(r"retry in ([\d.]+)s", re.IGNORECASE)
DAILY_QUOTA_PATTERN = re.compile(
    r"per day limit exceeded|EmbedContentRequestsPerDay", re.IGNORECASE
)


class EmbeddingError(RuntimeError):
    """Lỗi không thể phục hồi khi sinh embedding."""


class EmbeddingQuotaError(EmbeddingError):
    """Toàn bộ khóa đã cạn hạn mức request/ngày của free tier."""

    def __init__(self, message: str, *, done: int, total: int) -> None:
        super().__init__(message)
        self.done = done
        self.total = total


class _KeyQuotaExhausted(Exception):
    """Khóa hiện tại đã cạn hạn mức request/ngày; cần chuyển khóa kế tiếp."""


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    batches: int
    retries: int


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / EMBEDDING_CHARS_PER_TOKEN))


def normalize_api_keys(api_key: str | Sequence[str]) -> list[str]:
    source = [api_key] if isinstance(api_key, str) else list(api_key)
    keys: list[str] = []
    for item in source:
        for part in str(item).split(","):
            key = part.strip()
            if key and key not in keys:
                keys.append(key)
    return keys


class EmbeddingClient:
    def __init__(
        self,
        api_key: str | Sequence[str],
        model: str = EMBEDDING_MODEL,
        dimensions: int = EMBEDDING_DIM,
        batch_size: int = EMBEDDING_BATCH_SIZE,
        tokens_per_minute: int | None = EMBEDDING_TPM_LIMIT,
        max_tokens_per_request: int = EMBEDDING_MAX_TOKENS_PER_REQUEST,
        timeout: float = 90.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._keys = normalize_api_keys(api_key)
        if not self._keys:
            raise ValueError("Thiếu GEMINI_API_KEY để sinh embedding")
        if dimensions <= 0:
            raise ValueError("Số chiều embedding phải lớn hơn 0")
        if not 1 <= batch_size <= 100:
            raise ValueError("Kích thước lô embedding phải trong khoảng 1–100")
        if tokens_per_minute is not None and tokens_per_minute <= 0:
            raise ValueError("Hạn mức token mỗi phút phải lớn hơn 0")
        if max_tokens_per_request <= 0:
            raise ValueError("Số token tối đa mỗi request phải lớn hơn 0")
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.tokens_per_minute = tokens_per_minute
        self.max_tokens_per_request = max_tokens_per_request
        self._sleep = sleep
        self._key_index = 0
        self._quota_confirmed = False
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> EmbeddingClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @property
    def url(self) -> str:
        return EMBEDDING_URL.format(model=self.model)

    @property
    def key_count(self) -> int:
        return len(self._keys)

    def embed_texts(
        self,
        texts: Sequence[str],
        task_type: str = EMBEDDING_TASK_TYPE,
        progress: Callable[[int, int], None] | None = None,
        checkpoint: Callable[[int, list[list[float]]], None] | None = None,
    ) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(vectors=[], batches=0, retries=0)
        total = len(texts)
        vectors: list[list[float]] = []
        retries = 0
        batches = 0
        done = 0
        for batch, batch_tokens in self._plan_batches(list(texts)):
            if batches > 0 and self.tokens_per_minute is not None:
                self._sleep(batch_tokens * 60.0 / self.tokens_per_minute)
            while True:
                try:
                    batch_vectors, batch_retries = self._embed_batch(batch, task_type)
                except _KeyQuotaExhausted as exc:
                    if self._key_index + 1 >= len(self._keys):
                        raise EmbeddingQuotaError(
                            "Hạn mức request/ngày của toàn bộ khóa đã cạn: "
                            f"đã sinh {done}/{total} vector trong lần chạy này; "
                            "thêm khóa mới vào GEMINI_API_KEY rồi chạy lại để tiếp tục",
                            done=done,
                            total=total,
                        ) from exc
                    self._key_index += 1
                    self._quota_confirmed = False
                    continue
                break
            vectors.extend(batch_vectors)
            retries += batch_retries
            batches += 1
            done += len(batch)
            if progress is not None:
                progress(done, total)
            if checkpoint is not None:
                checkpoint(done, batch_vectors)
        return EmbeddingResult(vectors=vectors, batches=batches, retries=retries)

    def _plan_batches(self, texts: Sequence[str]) -> Iterator[tuple[list[str], int]]:
        batch: list[str] = []
        tokens = 0
        for text in texts:
            estimate = estimate_tokens(text)
            over_size = len(batch) >= self.batch_size
            over_tokens = tokens + estimate > self.max_tokens_per_request
            if batch and (over_size or over_tokens):
                yield batch, tokens
                batch, tokens = [], 0
            batch.append(text)
            tokens += estimate
        if batch:
            yield batch, tokens

    def _embed_batch(self, texts: list[str], task_type: str) -> tuple[list[list[float]], int]:
        for text in texts:
            if not text or not text.strip():
                raise EmbeddingError("Không thể sinh embedding cho nội dung rỗng")
            if estimate_tokens(text) > EMBEDDING_MAX_INPUT_TOKENS:
                raise EmbeddingError(
                    f"Đoạn văn vượt giới hạn {EMBEDDING_MAX_INPUT_TOKENS} token của mô hình"
                )
        payload = {
            "requests": [
                {
                    "model": f"models/{self.model}",
                    "content": {"parts": [{"text": text}]},
                    "taskType": task_type,
                    "outputDimensionality": self.dimensions,
                }
                for text in texts
            ]
        }
        retries = 0
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._client.post(
                    self.url,
                    headers={
                        "x-goog-api-key": self._keys[self._key_index],
                        "content-type": "application/json",
                    },
                    json=payload,
                )
            except httpx.HTTPError as exc:
                if attempt >= MAX_RETRIES:
                    raise EmbeddingError(
                        f"Lỗi mạng khi gọi Gemini sau {attempt + 1} lần thử"
                    ) from exc
                retries += 1
                self._delay(attempt, None)
                continue

            if response.status_code in RETRYABLE_STATUS:
                if self._is_daily_quota(response):
                    # Bản sao cũ của máy chủ có thể báo nhầm hạn mức ngày;
                    # xác nhận lại một lần trước khi coi khóa đã cạn.
                    if not self._quota_confirmed and attempt < MAX_RETRIES:
                        self._quota_confirmed = True
                        self._sleep(QUOTA_CONFIRM_DELAY_SECONDS)
                        continue
                    raise _KeyQuotaExhausted()
                if attempt >= MAX_RETRIES:
                    detail = response.text[:300].replace("\n", " ")
                    raise EmbeddingError(
                        f"Gemini trả mã {response.status_code} sau {attempt + 1} lần thử: {detail}"
                    )
                retries += 1
                self._delay(attempt, self._retry_after_seconds(response))
                continue

            if response.status_code >= 400:
                detail = response.text[:300].replace("\n", " ")
                raise EmbeddingError(f"Gemini trả mã {response.status_code}: {detail}")

            try:
                data = response.json()
            except ValueError as exc:
                raise EmbeddingError("Phản hồi Gemini không phải JSON hợp lệ") from exc
            embeddings = data.get("embeddings")
            if not isinstance(embeddings, list) or len(embeddings) != len(texts):
                raise EmbeddingError("Số vector Gemini trả về không khớp số đoạn văn bản gửi đi")
            return self._validate_vectors(embeddings), retries
        raise AssertionError("Vòng lặp thử lại không bao giờ kết thúc")

    def _is_daily_quota(self, response: httpx.Response) -> bool:
        return response.status_code == 429 and bool(DAILY_QUOTA_PATTERN.search(response.text))

    def _validate_vectors(self, embeddings: list[object]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for item in embeddings:
            values = item.get("values") if isinstance(item, dict) else None
            if not isinstance(values, list) or len(values) != self.dimensions:
                raise EmbeddingError(f"Vector Gemini không đúng {self.dimensions} chiều")
            vector: list[float] = []
            for value in values:
                if isinstance(value, bool) or not isinstance(value, int | float):
                    raise EmbeddingError("Vector Gemini chứa giá trị không phải số")
                number = float(value)
                if not math.isfinite(number):
                    raise EmbeddingError("Vector Gemini chứa giá trị không hữu hạn")
                vector.append(number)
            vectors.append(vector)
        return vectors

    def _retry_after_seconds(self, response: httpx.Response) -> float | None:
        header = response.headers.get("retry-after")
        if header:
            try:
                return float(header)
            except ValueError:
                pass
        match = RETRY_IN_PATTERN.search(response.text[:2000])
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    def _delay(self, attempt: int, retry_after: float | None) -> None:
        if retry_after is not None and retry_after > 0:
            self._sleep(min(retry_after, MAX_RETRY_AFTER_SECONDS))
            return
        delay = BASE_DELAY_SECONDS * (2**attempt) + random.uniform(0, 0.5)
        self._sleep(delay)


def vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(f"{value:.7g}" for value in values) + "]"
