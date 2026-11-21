from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChunkRecord:
    """Một chunk con cùng nội dung mục cha để mở rộng ngữ cảnh."""

    child_id: str
    parent_id: str | None
    content: str
    parent_content: str | None
    document: str
    section: str | None
    heading: str | None
    page: int | None
    token_count: int | None
    parent_token_count: int | None
    metadata: dict[str, Any] = field(default_factory=dict)
    vector_score: float | None = None
    lexical_score: float | None = None
    trigram_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None
    final_score: float | None = None
    rank: int | None = None

    @property
    def context_content(self) -> str:
        return self.parent_content or self.content

    @property
    def context_token_count(self) -> int:
        return self.parent_token_count or self.token_count or 0


@dataclass(frozen=True)
class QueryClassification:
    query_type: str
    confidence: float
    source: str
    k_min: int
    k_max: int
    evidence: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievedChunk:
    rank: int
    child_id: str
    parent_id: str | None
    content: str
    child_content: str
    document: str
    section: str | None
    heading: str | None
    page: int | None
    score: float
    scores: dict[str, float | None]
    document_title: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "child_id": self.child_id,
            "parent_id": self.parent_id,
            "content": self.content,
            "child_content": self.child_content,
            "document": self.document,
            "section": self.section,
            "heading": self.heading,
            "page": self.page,
            "score": self.score,
            "scores": self.scores,
            "document_title": self.document_title,
        }


@dataclass(frozen=True)
class DecompositionResult:
    subqueries: list[str]
    source: str


@dataclass
class RetrievalResult:
    query: str
    normalized_query: str
    query_type: str
    classification_source: str
    classification_confidence: float
    subqueries: list[str]
    decomposition_source: str
    chunks: list[RetrievedChunk]
    k: int
    timings_ms: dict[str, float]
    cache_hit: bool = False
    rerank_fallback: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "normalized_query": self.normalized_query,
            "query_type": self.query_type,
            "classification_source": self.classification_source,
            "classification_confidence": self.classification_confidence,
            "subqueries": self.subqueries,
            "decomposition_source": self.decomposition_source,
            "k": self.k,
            "timings_ms": self.timings_ms,
            "cache_hit": self.cache_hit,
            "rerank_fallback": self.rerank_fallback,
            "chunks": [chunk.as_dict() for chunk in self.chunks],
        }
