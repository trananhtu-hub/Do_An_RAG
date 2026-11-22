from __future__ import annotations

from collections.abc import Iterator, Sequence

from .base import LLMError, LLMMessage, LLMProvider, LLMResponse, StreamDelta


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

    def complete_stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        thinking_level: str | None = None,
        max_output_tokens: int | None = None,
        json_mode: bool = True,
        timeout_ms: int | None = None,
    ) -> Iterator[StreamDelta]:
        """Stream qua từng provider; chỉ chuyển dự phòng khi chưa phát token nào."""
        errors: list[str] = []
        for index, provider in enumerate(self._providers):
            emitted = False
            final: StreamDelta | None = None
            try:
                iterator = self._stream_provider(
                    provider,
                    messages,
                    thinking_level=thinking_level,
                    max_output_tokens=max_output_tokens,
                    json_mode=json_mode,
                    timeout_ms=timeout_ms,
                )
                try:
                    for delta in iterator:
                        if delta.done:
                            final = delta
                            continue
                        if delta.text:
                            emitted = True
                            yield delta
                finally:
                    close = getattr(iterator, "close", None)
                    if close is not None:
                        close()
                if final is None or final.response is None:
                    raise LLMError(
                        "Provider streaming không trả kết quả cuối",
                        provider=provider.name,
                    )
                response = final.response
                if index > 0:
                    response = LLMResponse(
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
                yield StreamDelta(response=response, done=True)
                return
            except LLMError as exc:
                errors.append(f"{provider.name}: {exc}")
                if emitted:
                    raise
                continue
        raise FallbackExhausted(
            "Toàn bộ provider streaming đều thất bại — " + " | ".join(errors),
            attempts=tuple(provider.name for provider in self._providers),
        )

    def _stream_provider(
        self,
        provider: LLMProvider,
        messages: Sequence[LLMMessage],
        *,
        thinking_level: str | None,
        max_output_tokens: int | None,
        json_mode: bool,
        timeout_ms: int | None,
    ) -> Iterator[StreamDelta]:
        method = getattr(provider, "complete_stream", None)
        if method is None:
            yield StreamDelta(
                response=provider.complete(
                    messages,
                    thinking_level=thinking_level,
                    max_output_tokens=max_output_tokens,
                    json_mode=json_mode,
                    timeout_ms=timeout_ms,
                ),
                done=True,
            )
            return
        yield from method(
            messages,
            thinking_level=thinking_level,
            max_output_tokens=max_output_tokens,
            json_mode=json_mode,
            timeout_ms=timeout_ms,
        )

    def close(self) -> None:
        for provider in self._providers:
            provider.close()
