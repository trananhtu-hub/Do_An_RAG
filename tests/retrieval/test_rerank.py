from __future__ import annotations

import time

from app.services.retrieval.rerank import TimeoutReranker


class FakeReranker:
    def __init__(
        self,
        scores: list[float] | None = None,
        *,
        delay: float = 0.0,
        error: Exception | None = None,
    ) -> None:
        self.scores = scores or []
        self.delay = delay
        self.error = error
        self.closed = False

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.scores

    def close(self) -> None:
        self.closed = True


def test_scores_are_returned_in_order() -> None:
    wrapper = TimeoutReranker(FakeReranker([0.2, 0.9, 0.5]), timeout_ms=1000)
    try:
        attempt = wrapper.score("q", ["a", "b", "c"])
    finally:
        wrapper.close()
    assert attempt.scores == [0.2, 0.9, 0.5]
    assert attempt.error is None


def test_timeout_returns_fallback_marker() -> None:
    wrapper = TimeoutReranker(FakeReranker([0.1], delay=0.3), timeout_ms=50)
    try:
        started = time.perf_counter()
        attempt = wrapper.score("q", ["a"])
        elapsed = time.perf_counter() - started
    finally:
        wrapper.close()
    assert attempt.scores is None
    assert attempt.error == "timeout"
    assert elapsed < 0.25


def test_model_error_returns_typed_marker() -> None:
    wrapper = TimeoutReranker(FakeReranker(error=RuntimeError("hỏng")), timeout_ms=1000)
    try:
        attempt = wrapper.score("q", ["a"])
    finally:
        wrapper.close()
    assert attempt.scores is None
    assert attempt.error == "error:RuntimeError"


def test_length_mismatch_is_rejected() -> None:
    wrapper = TimeoutReranker(FakeReranker([0.1]), timeout_ms=1000)
    try:
        attempt = wrapper.score("q", ["a", "b"])
    finally:
        wrapper.close()
    assert attempt.scores is None
    assert attempt.error == "error:length_mismatch"


def test_empty_documents_return_empty_scores() -> None:
    wrapper = TimeoutReranker(FakeReranker([]), timeout_ms=1000)
    try:
        attempt = wrapper.score("q", [])
    finally:
        wrapper.close()
    assert attempt.scores == []
    assert attempt.error is None


def test_rejects_non_positive_timeout() -> None:
    try:
        TimeoutReranker(FakeReranker([]), timeout_ms=0)
    except ValueError:
        return
    raise AssertionError("phải ném ValueError")
