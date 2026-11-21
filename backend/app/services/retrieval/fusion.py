from __future__ import annotations

from dataclasses import dataclass

from .types import ChunkRecord


@dataclass(frozen=True)
class RankedList:
    label: str
    records: list[ChunkRecord]
    weight: float


def rrf_fuse(lists: list[RankedList], k: int, limit: int | None = None) -> list[ChunkRecord]:
    """Hợp nhất xếp hạng bằng Reciprocal Rank Fusion.

    score(d) = sum(weight_l / (k + rank_l(d))), rank bắt đầu từ 1.
    """
    if k <= 0:
        raise ValueError("RRF k phải lớn hơn 0")
    scores: dict[str, float] = {}
    best_rank: dict[str, int] = {}
    registry: dict[str, ChunkRecord] = {}
    for ranked in lists:
        if ranked.weight <= 0:
            continue
        for rank, record in enumerate(ranked.records, start=1):
            key = record.child_id
            if key not in registry:
                registry[key] = record
                best_rank[key] = rank
            else:
                best_rank[key] = min(best_rank[key], rank)
            scores[key] = scores.get(key, 0.0) + ranked.weight / (k + rank)
            merged = registry[key]
            if ranked.label == "vector":
                merged.vector_score = record.vector_score
            elif ranked.label == "lexical":
                merged.lexical_score = record.lexical_score
            elif ranked.label == "trigram":
                merged.trigram_score = record.trigram_score
    ordered = sorted(
        registry.values(),
        key=lambda item: (-scores[item.child_id], best_rank[item.child_id], item.child_id),
    )
    for record in ordered:
        record.rrf_score = scores[record.child_id]
    return ordered[:limit] if limit is not None else ordered
