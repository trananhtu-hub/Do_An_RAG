from __future__ import annotations

from collections.abc import Sequence

from .base import LLMError, LLMMessage, LLMProvider, LLMResponse


class FallbackExhausted(LLMError):
    """Toàn bộ provider trong chain đều thất bại."""

    def __init__(self, message: str, *, attempts: Sequence[str]) -> None:
        super().__init__(message, provider="fallback_chain", retryable=False)
        self.attempts = tuple(attempts)


class FallbackChain:
    """Gọi lần lượt các provider theo thứ tự cấu hình.

    Không che giấu lỗi: khi tất cả thất bại, FallbackExhausted giữ lại thông báo
    của từng provider để chẩn đoán.
    """

    def __init__(self, providers: Sequence[LLMProvider]) -> None:
        if not providers:
            raise ValueError("FallbackChain cần ít nhất một provider")
        self._providers = list(providers)

    @property
    def providers(self) -> tuple[LLMProvider, ...]:
        return tuple(self._providers)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(provider.name for provider in self._providers)

    def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        thinking_level: str | None = None,
        max_output_tokens: int | None = None,
        json_mode: bool = True,
        timeout_ms: int | None = None,
    ) -> LLMResponse:
        errors: list[str] = []
        for index, provider in enumerate(self._providers):
            try:
                response = provider.complete(
                    messages,
                    thinking_level=thinking_level,
                    max_output_tokens=max_output_tokens,
                    json_mode=json_mode,
                    timeout_ms=timeout_ms,
                )
            except LLMError as exc:
                errors.append(f"{provider.name}: {exc}")
                continue
            if index == 0:
                return response
            return LLMResponse(
                text=response.text,
                model=response.model,
                provider=response.provider,
                usage=response.usage,
                latency_ms=response.latency_ms,
                cost_usd=response.cost_usd,
                finish_reason=response.finish_reason,
                fallback_used=provider.name,
                attempts=tuple(item.name for item in self._providers[: index + 1]),
                raw=response.raw,
            )
        raise FallbackExhausted(
            "Toàn bộ provider đều thất bại — " + " | ".join(errors),
            attempts=tuple(provider.name for provider in self._providers),
        )

    def close(self) -> None:
        for provider in self._providers:
            provider.close()
