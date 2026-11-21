from __future__ import annotations

import pytest
from app.services.generation.providers import (
    FallbackChain,
    FallbackExhausted,
    LLMError,
    LLMMessage,
    LLMResponse,
    Usage,
)

MESSAGES = [LLMMessage(role="user", content="hỏi")]


class Stub:
    model = "m"

    def __init__(self, name: str, *, fail: bool = False) -> None:
        self.name = name
        self.fail = fail
        self.calls = 0

    def complete(self, messages, **kwargs) -> LLMResponse:
        self.calls += 1
        if self.fail:
            raise LLMError("hỏng", provider=self.name, retryable=False)
        return LLMResponse(
            text="ok",
            model=self.model,
            provider=self.name,
            usage=Usage.from_counts(10, 5),
        )

    def close(self) -> None:
        pass


def test_primary_answers_without_fallback_flag() -> None:
    chain = FallbackChain([Stub("a"), Stub("b")])
    response = chain.complete(MESSAGES)
    assert response.provider == "a"
    assert response.fallback_used is None
    assert response.attempts == ()


def test_falls_back_when_primary_fails() -> None:
    primary, secondary = Stub("a", fail=True), Stub("b")
    response = FallbackChain([primary, secondary]).complete(MESSAGES)
    assert response.provider == "b"
    assert response.fallback_used == "b"
    assert response.attempts == ("a", "b")
    assert primary.calls == 1 and secondary.calls == 1


def test_all_fail_raises_with_attempts() -> None:
    chain = FallbackChain([Stub("a", fail=True), Stub("b", fail=True)])
    with pytest.raises(FallbackExhausted) as info:
        chain.complete(MESSAGES)
    assert info.value.attempts == ("a", "b")
    assert "a: hỏng" in str(info.value)


def test_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError):
        FallbackChain([])


def test_close_closes_all() -> None:
    class CloseTracking(Stub):
        def __init__(self, name: str) -> None:
            super().__init__(name)
            self.closed = False

        def close(self) -> None:
            self.closed = True

    providers = [CloseTracking("a"), CloseTracking("b")]
    FallbackChain(providers).close()
    assert all(provider.closed for provider in providers)
