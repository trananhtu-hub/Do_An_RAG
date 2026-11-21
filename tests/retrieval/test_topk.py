from __future__ import annotations

import pytest
from app.services.retrieval.config import TopKConfig
from app.services.retrieval.topk import select_top_k
from app.services.retrieval.types import ChunkRecord, QueryClassification


def _record(index: int, score: float, tokens: int = 100) -> ChunkRecord:
    record = ChunkRecord(
        child_id=f"c{index}",
        parent_id=f"p{index}",
        content="nội dung",
        parent_content=None,
        document="doc.pdf",
        section=f"Mục {index}",
        heading=None,
        page=1,
        token_count=tokens,
        parent_token_count=tokens,
    )
    record.final_score = score
    return record


def _classification(query_type: str = "tra_cuu", k_min: int = 3, k_max: int = 5):
    return QueryClassification(
        query_type=query_type, confidence=0.9, source="heuristic", k_min=k_min, k_max=k_max
    )


def test_override_limits_without_adaptive_logic() -> None:
    chunks = [_record(index, 1.0 - index / 10) for index in range(6)]
    selected = select_top_k(chunks, _classification(), TopKConfig(), override=2)
    assert [record.child_id for record in selected] == ["c0", "c1"]
    assert [record.rank for record in selected] == [1, 2]


def test_fixed_mode_uses_default() -> None:
    chunks = [_record(index, 1.0) for index in range(6)]
    config = TopKConfig(adaptive=False, default=4)
    selected = select_top_k(chunks, _classification(), config)
    assert len(selected) == 4


def test_adaptive_stops_at_relative_score_floor() -> None:
    chunks = [
        _record(0, 1.0),
        _record(1, 0.9),
        _record(2, 0.4),
        _record(3, 0.3),
    ]
    config = TopKConfig(adaptive=True, min=3, max=5, relative_score_floor=0.5)
    selected = select_top_k(chunks, _classification(k_min=3, k_max=5), config)
    assert [record.child_id for record in selected] == ["c0", "c1", "c2"]


def test_adaptive_never_exceeds_type_range() -> None:
    chunks = [_record(index, 1.0) for index in range(10)]
    config = TopKConfig(adaptive=True, min=3, max=8)
    selected = select_top_k(chunks, _classification(k_min=3, k_max=3), config)
    assert len(selected) == 3


def test_token_budget_stops_after_minimum() -> None:
    chunks = [_record(index, 1.0, tokens=4000) for index in range(5)]
    config = TopKConfig(adaptive=True, min=3, max=5, token_budget=6000)
    selected = select_top_k(chunks, _classification(k_min=3, k_max=5), config)
    assert len(selected) == 3


def test_override_rejects_non_positive_value() -> None:
    with pytest.raises(ValueError):
        select_top_k([_record(0, 1.0)], _classification(), TopKConfig(), override=0)


def test_empty_input_returns_empty() -> None:
    assert select_top_k([], _classification(), TopKConfig()) == []
