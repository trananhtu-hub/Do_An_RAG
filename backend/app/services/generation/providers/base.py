from __future__ import annotations

import math
import random
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in ("system", "user", "assistant"):
            raise ValueError(f"Vai trò không hợp lệ: {self.role}")


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_counts(cls, input_tokens: int, output_tokens: int) -> Usage:
        return cls(
            input_tokens=max(0, input_tokens),
            output_tokens=max(0, output_tokens),
            total_tokens=max(0, input_tokens) + max(0, output_tokens),
        )


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    provider: str
    usage: Usage = field(default_factory=Usage)
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    finish_reason: str | None = None
    fallback_used: str | None = None
    attempts: tuple[str, ...] = ()
    raw: dict[str, Any] | None = None


class LLMError(RuntimeError):
    """Lỗi gọi LLM; retryable quyết định adapter có thử lại hay không."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable
        self.status_code = status_code


class LLMConfigurationError(LLMError):
    """Thiếu cấu hình hoặc khóa; không thử lại và không tính là lỗi tạm thời."""


@dataclass(frozen=True)
class StreamDelta:
    """Một mẩu đầu ra streaming; mẩu cuối mang LLMResponse đầy đủ."""

    text: str = ""
    response: LLMResponse | None = None
    done: bool = False


class LLMProvider(Protocol):
    name: str
    model: str

    def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        thinking_level: str | None = None,
        max_output_tokens: int | None = None,
        json_mode: bool = True,
        timeout_ms: int | None = None,
    ) -> LLMResponse: ...

    def complete_stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        thinking_level: str | None = None,
        max_output_tokens: int | None = None,
        json_mode: bool = True,
        timeout_ms: int | None = None,
    ) -> Iterator[StreamDelta]: ...

    def close(self) -> None: ...


def estimate_usage(
    messages: Sequence[LLMMessage],
    text: str,
    *,
    chars_per_token: float = 3.5,
) -> Usage:
    """Ước lượng token khi endpoint streaming không trả usage."""
    prompt_chars = sum(len(message.content) for message in messages)
    scale = max(chars_per_token, 0.1)
    return Usage.from_counts(
        math.ceil(prompt_chars / scale),
        math.ceil(len(text) / scale),
    )


def retry_call(
    function: Callable[[], LLMResponse],
    *,
    max_retries: int,
    backoff_base_s: float,
    backoff_max_s: float,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
) -> LLMResponse:
    """Gọi hàm với backoff lũy thừa; chỉ thử lại lỗi được đánh dấu retryable."""
    attempt = 0
    while True:
        try:
            return function()
        except LLMError as exc:
            if not exc.retryable or attempt >= max_retries:
                raise
            delay = min(backoff_max_s, backoff_base_s * (2**attempt))
            sleep(delay + jitter() * min(backoff_base_s, 1.0))
            attempt += 1
