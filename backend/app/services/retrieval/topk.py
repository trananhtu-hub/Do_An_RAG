from __future__ import annotations

from .config import TopKConfig
from .types import ChunkRecord, QueryClassification


def select_top_k(
    chunks: list[ChunkRecord],
    classification: QueryClassification,
    config: TopKConfig,
    *,
    override: int | None = None,
) -> list[ChunkRecord]:
    """Chọn số chunk theo loại truy vấn, điểm và ngân sách token."""
    if not chunks:
        return []
    if override is not None:
        if override <= 0:
            raise ValueError("top_k phải lớn hơn 0")
        selected = chunks[: min(override, len(chunks))]
    elif not config.adaptive:
        selected = chunks[: min(config.default, len(chunks))]
    else:
        k_min = min(max(classification.k_min, config.min), config.max, len(chunks))
        k_max = min(max(classification.k_max, k_min), config.max)
        best = chunks[0].final_score or 0.0
        used_tokens = 0
        selected = []
        for record in chunks:
            if len(selected) >= k_max:
                break
            score = record.final_score or 0.0
            if len(selected) >= k_min:
                if best > 0 and score < best * config.relative_score_floor:
                    break
                if used_tokens + record.context_token_count > config.token_budget:
                    break
            selected.append(record)
            used_tokens += record.context_token_count
    for rank, record in enumerate(selected, start=1):
        record.rank = rank
    return selected
