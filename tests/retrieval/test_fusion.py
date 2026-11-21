from __future__ import annotations

import pytest
from app.services.retrieval.fusion import RankedList, rrf_fuse
from app.services.retrieval.types import ChunkRecord


def _record(child_id: str) -> ChunkRecord:
    return ChunkRecord(
        child_id=child_id,
        parent_id=f"p-{child_id}",
        content=f"nội dung {child_id}",
        parent_content=None,
        document="doc.pdf",
        section="Mục 1",
        heading=None,
        page=1,
        token_count=10,
        parent_token_count=20,
    )


def test_rrf_uses_exact_weighted_formula() -> None:
    a, b, c = _record("a"), _record("b"), _record("c")
    fused = rrf_fuse([RankedList("vector", [a, b], 1.0), RankedList("lexical", [b, c], 0.3)], k=60)
    scores = {record.child_id: record.rrf_score for record in fused}
    assert scores["a"] == pytest.approx(1 / 61)
    assert scores["b"] == pytest.approx(1 / 62 + 0.3 / 61)
    assert scores["c"] == pytest.approx(0.3 / 62)


def test_rrf_orders_by_score_then_best_rank_then_id() -> None:
    a, b, c = _record("a"), _record("b"), _record("c")
    fused = rrf_fuse([RankedList("vector", [a, b], 1.0), RankedList("lexical", [b, c], 0.3)], k=60)
    assert [record.child_id for record in fused] == ["b", "a", "c"]


def test_rrf_deduplicates_same_child_and_merges_branch_scores() -> None:
    a = _record("a")
    a.vector_score = 0.9
    a_again = _record("a")
    a_again.lexical_score = 0.4
    fused = rrf_fuse([RankedList("vector", [a], 1.0), RankedList("lexical", [a_again], 0.3)], k=60)
    assert len(fused) == 1
    assert fused[0].vector_score == 0.9
    assert fused[0].lexical_score == 0.4
    assert fused[0].rrf_score == pytest.approx(1 / 61 + 0.3 / 61)


def test_rrf_applies_limit_and_skips_zero_weights() -> None:
    records = [_record(str(index)) for index in range(4)]
    fused = rrf_fuse(
        [RankedList("vector", records, 1.0), RankedList("lexical", records, 0.0)],
        k=60,
        limit=2,
    )
    assert [record.child_id for record in fused] == ["0", "1"]


def test_rrf_rejects_non_positive_k() -> None:
    with pytest.raises(ValueError):
        rrf_fuse([], k=0)
