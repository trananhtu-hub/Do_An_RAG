from __future__ import annotations

import pytest
from app.services.retrieval.cache import TTLCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_get_returns_cached_value_before_expiry() -> None:
    clock = FakeClock()
    cache: TTLCache[str] = TTLCache(10, 4, clock)
    cache.set("k", "v")
    clock.now = 9.9
    assert cache.get("k") == "v"
    assert cache.hits == 1


def test_value_expires_at_ttl_boundary() -> None:
    clock = FakeClock()
    cache: TTLCache[str] = TTLCache(10, 4, clock)
    cache.set("k", "v")
    clock.now = 10.0
    assert cache.get("k") is None
    assert cache.expired == 1
    assert cache.misses == 1
    assert len(cache) == 0


def test_lru_evicts_oldest_entry_when_full() -> None:
    clock = FakeClock()
    cache: TTLCache[int] = TTLCache(60, 2, clock)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")
    cache.set("c", 3)
    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_rejects_invalid_construction_parameters() -> None:
    with pytest.raises(ValueError):
        TTLCache(0, 4)
    with pytest.raises(ValueError):
        TTLCache(10, 0)
