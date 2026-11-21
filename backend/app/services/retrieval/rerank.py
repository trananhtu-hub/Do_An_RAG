from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Protocol


class RerankerError(RuntimeError):
    pass


class Reranker(Protocol):
    def rerank(self, query: str, documents: list[str]) -> list[float]: ...


class CrossEncoderReranker:
    """bge-reranker-v2-m3 chạy cục bộ; nạp mô hình theo nhu cầu (lazy)."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        *,
        batch_size: int = 16,
        max_length: int = 512,
        device: str = "auto",
        precision: str = "fp16",
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self.device_setting = device
        self.precision = precision
        self._torch: Any = None
        self._tokenizer: Any = None
        self._model: Any = None
        self._device: str | None = None

    def warmup(self) -> None:
        self._ensure_model()
        self.rerank("khởi động", ["khởi động mô hình xếp hạng lại"])

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - phụ thuộc tùy chọn
            raise RerankerError(
                "Chưa cài torch/transformers; xem backend/requirements-retrieval.txt"
            ) from exc

        device = self.device_setting
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if (device == "cuda" and self.precision == "fp16") else torch.float32
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        model = AutoModelForSequenceClassification.from_pretrained(self.model_name, dtype=dtype)
        model.to(device)
        model.eval()
        self._torch = torch
        self._tokenizer = tokenizer
        self._model = model
        self._device = device

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        self._ensure_model()
        torch = self._torch
        scores: list[float] = []
        with torch.inference_mode():
            for start in range(0, len(documents), self.batch_size):
                batch = documents[start : start + self.batch_size]
                features = self._tokenizer(
                    [query] * len(batch),
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )
                features = {key: value.to(self._device) for key, value in features.items()}
                logits = self._model(**features).logits.view(-1).float()
                scores.extend(torch.sigmoid(logits).cpu().tolist())
        return scores

    def close(self) -> None:
        self._model = None
        self._tokenizer = None
        if self._torch is not None and self._device == "cuda":  # pragma: no cover
            self._torch.cuda.empty_cache()


@dataclass(frozen=True)
class RerankAttempt:
    scores: list[float] | None
    error: str | None
    elapsed_ms: float


class TimeoutReranker:
    """Bọc reranker với hạn thời gian; lỗi/quá hạn trả về None để fallback RRF."""

    def __init__(self, reranker: Reranker, timeout_ms: int) -> None:
        if timeout_ms <= 0:
            raise ValueError("timeout_ms phải lớn hơn 0")
        self._reranker = reranker
        self._timeout = timeout_ms / 1000.0
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rerank")

    def warmup(self) -> None:
        warmup = getattr(self._reranker, "warmup", None)
        if callable(warmup):
            warmup()

    def score(self, query: str, documents: list[str]) -> RerankAttempt:
        started = time.perf_counter()
        future = self._executor.submit(self._reranker.rerank, query, documents)
        try:
            scores = future.result(timeout=self._timeout)
        except FuturesTimeoutError:
            self._restart_executor()
            return RerankAttempt(None, "timeout", (time.perf_counter() - started) * 1000)
        except Exception as exc:  # noqa: BLE001 - fallback có chủ đích cho mọi lỗi mô hình
            return RerankAttempt(
                None, f"error:{type(exc).__name__}", (time.perf_counter() - started) * 1000
            )
        if len(scores) != len(documents):
            return RerankAttempt(
                None, "error:length_mismatch", (time.perf_counter() - started) * 1000
            )
        return RerankAttempt(scores, None, (time.perf_counter() - started) * 1000)

    def _restart_executor(self) -> None:
        # Luồng đang chạy có thể còn bận; bỏ executor cũ để truy vấn sau không bị chặn.
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rerank")

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
        close = getattr(self._reranker, "close", None)
        if callable(close):
            close()
