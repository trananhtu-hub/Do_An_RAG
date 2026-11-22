from __future__ import annotations

from dataclasses import replace

import pytest
from app.services.retrieval.config import RetrievalConfig
from app.services.retrieval.rerank import TimeoutReranker
from app.services.retrieval.service import RetrievalService
from app.services.retrieval.types import ChunkRecord


def _record(
    child_id: str,
    parent_id: str | None = None,
    content: str | None = None,
    section: str | None = None,
    document: str = "doc.pdf",
):
    return ChunkRecord(
        child_id=child_id,
        parent_id=parent_id or f"p-{child_id}",
        content=content or f"child {child_id}",
        parent_content=None,
        document=document,
        section=section or f"Mục {child_id}",
        heading=None,
        page=1,
        token_count=100,
        parent_token_count=200,
    )


def _config(**overrides: object) -> RetrievalConfig:
    base = RetrievalConfig.from_dict({})
    return base.with_overrides(
        {
            "latency": {"subquery_workers": 1},
            "cache": {"enabled": False},
            "rerank": {"enabled": False},
            "classifier": {"llm_enabled": False},
            "decomposition": {"enabled": False},
            "top_k": {"adaptive": False, "default": 5},
            **overrides,
        }
    )


class FakeStore:
    def __init__(
        self,
        vector: list[ChunkRecord] | None = None,
        lexical: list[ChunkRecord] | None = None,
        trigram: list[ChunkRecord] | None = None,
        parents: dict[str, str] | None = None,
    ) -> None:
        self.vector = vector or []
        self.lexical = lexical or []
        self.trigram = trigram or []
        self.parents = parents or {}
        self.vector_calls = 0
        self.parent_calls: list[list[str]] = []

    def vector_search(self, vector, limit, threshold, exclude_kinds=()):  # noqa: ANN001
        self.vector_calls += 1
        self.exclude_kinds = tuple(exclude_kinds)
        records = [replace(record) for record in self.vector[:limit]]
        for index, record in enumerate(records):
            record.vector_score = 1.0 - index / 10
        return records

    def lexical_search(self, tsquery, limit, exclude_kinds=()):  # noqa: ANN001
        records = [replace(record) for record in self.lexical[:limit]]
        for index, record in enumerate(records):
            record.lexical_score = 1.0 - index / 10
        return records

    def trigram_search(self, terms, limit, min_matched_terms, exclude_kinds=()):  # noqa: ANN001
        records = [replace(record) for record in self.trigram[:limit]]
        for index, record in enumerate(records):
            record.trigram_score = 1.0 - index / 10
        return records

    def fetch_parents(self, parent_ids):
        self.parent_calls.append(list(parent_ids))
        return {
            parent_id: self.parents.get(parent_id, f"parent {parent_id}")
            for parent_id in parent_ids
        }


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_queries(self, queries: list[str]) -> list[list[float]]:
        self.calls.append(list(queries))
        return [[0.1, 0.2, 0.3] for _ in queries]


class FakeLLM:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.payload = payload
        self.calls = 0

    def generate_json(self, model: str, prompt: str, timeout_ms: int) -> dict[str, object] | None:
        self.calls += 1
        return self.payload

    def close(self) -> None:
        pass


class FakeReranker:
    def __init__(self, scores: list[float] | None = None, *, delay: float = 0.0) -> None:
        self.scores = scores or []
        self.delay = delay
        self.documents: list[str] = []

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        self.documents = list(documents)
        if self.delay:
            import time

            time.sleep(self.delay)
        return self.scores


def _service(
    config: RetrievalConfig,
    store: FakeStore,
    *,
    reranker: TimeoutReranker | None = None,
    llm: FakeLLM | None = None,
) -> RetrievalService:
    return RetrievalService(
        config,
        store,  # type: ignore[arg-type]
        FakeEmbedder(),  # type: ignore[arg-type]
        reranker=reranker,
        llm=llm,  # type: ignore[arg-type]
    )


def test_vector_only_returns_chunks_with_parent_context() -> None:
    store = FakeStore(vector=[_record("a"), _record("b"), _record("c")])
    service = _service(_config(lexical={"enabled": False}), store)
    try:
        result = service.retrieve("S3 là gì", top_k=2)
    finally:
        service.close()
    assert result.k == 2
    assert [chunk.child_id for chunk in result.chunks] == ["a", "b"]
    assert result.chunks[0].content == "parent p-a"
    assert result.chunks[0].child_content == "child a"
    assert all(key in result.timings_ms for key in ("vector_ms", "search_ms", "total_ms"))


def test_hybrid_fusion_orders_by_rrf_and_merges_scores() -> None:
    store = FakeStore(vector=[_record("a"), _record("b")], lexical=[_record("b"), _record("c")])
    service = _service(_config(), store)
    try:
        result = service.retrieve("truy vấn")
    finally:
        service.close()
    assert [chunk.child_id for chunk in result.chunks] == ["b", "a", "c"]
    top = result.chunks[0]
    assert top.scores["vector"] is not None
    assert top.scores["lexical"] is not None


def test_reranker_reorders_candidates_and_sets_score() -> None:
    store = FakeStore(vector=[_record("a"), _record("b"), _record("c")])
    reranker = TimeoutReranker(FakeReranker([0.1, 0.9, 0.5]), timeout_ms=1000)
    service = _service(_config(rerank={"enabled": True}), store, reranker=reranker)
    try:
        result = service.retrieve("truy vấn")
    finally:
        service.close()
    assert [chunk.child_id for chunk in result.chunks] == ["b", "c", "a"]
    assert result.chunks[0].score == pytest.approx(0.9)
    assert result.rerank_fallback is None


def test_rerank_scores_parent_content_with_context_header() -> None:
    store = FakeStore(vector=[_record("a"), _record("b")])
    fake = FakeReranker([0.9, 0.1])
    reranker = TimeoutReranker(fake, timeout_ms=1000)
    service = _service(
        _config(rerank={"enabled": True, "content_scope": "parent"}),
        store,
        reranker=reranker,
    )
    try:
        service.retrieve("truy vấn")
    finally:
        service.close()
    assert fake.documents[0] == "doc.pdf - Mục a\nparent p-a"


def test_rerank_scores_child_content_when_scope_is_child() -> None:
    store = FakeStore(vector=[_record("a")], parents={"p-a": "parent p-a"})
    fake = FakeReranker([0.9])
    reranker = TimeoutReranker(fake, timeout_ms=1000)
    service = _service(
        _config(rerank={"enabled": True, "content_scope": "child"}),
        store,
        reranker=reranker,
    )
    try:
        service.retrieve("truy vấn")
    finally:
        service.close()
    assert fake.documents[0] == "doc.pdf - Mục a\nchild a"


def test_rerank_winner_is_kept_when_same_section_is_deduplicated() -> None:
    store = FakeStore(
        vector=[
            _record("a", section="Mục 1"),
            _record("b", section="Mục 1"),
        ]
    )
    fake = FakeReranker([0.1, 0.9])
    reranker = TimeoutReranker(fake, timeout_ms=1000)
    service = _service(
        _config(rerank={"enabled": True, "content_scope": "child"}),
        store,
        reranker=reranker,
    )
    try:
        result = service.retrieve("truy vấn")
    finally:
        service.close()
    assert [chunk.child_id for chunk in result.chunks] == ["b"]
    assert result.chunks[0].score == 0.9


def _kind_record(child_id: str, kind: str):
    record = _record(child_id)
    record.metadata["kind"] = kind
    return record


def _source_filter_config() -> RetrievalConfig:
    return _config(
        rerank={
            "enabled": True,
            "source_filter": {
                "enabled": True,
                "exclude_kinds": ["question"],
                "bypass_patterns": [r"\bcâu\s*\d+"],
            },
        }
    )


def test_source_filter_excludes_question_chunks_from_rerank_pool() -> None:
    store = FakeStore(vector=[_kind_record("q", "question"), _kind_record("t", "theory")])
    fake = FakeReranker([0.1])
    reranker = TimeoutReranker(fake, timeout_ms=1000)
    service = _service(_source_filter_config(), store, reranker=reranker)
    try:
        result = service.retrieve("So sánh chi phí lưu trữ S3")
    finally:
        service.close()
    assert fake.documents == ["doc.pdf - Mục t\nchild t"]
    assert [chunk.child_id for chunk in result.chunks] == ["t"]


def test_source_filter_bypass_when_query_names_question_number() -> None:
    store = FakeStore(vector=[_kind_record("q", "question"), _kind_record("t", "theory")])
    fake = FakeReranker([0.9, 0.1])
    reranker = TimeoutReranker(fake, timeout_ms=1000)
    service = _service(_source_filter_config(), store, reranker=reranker)
    try:
        service.retrieve("Giải thích đáp án câu 249")
    finally:
        service.close()
    assert len(fake.documents) == 2


def test_reranker_timeout_falls_back_to_rrf_order() -> None:
    store = FakeStore(vector=[_record("a"), _record("b")])
    reranker = TimeoutReranker(FakeReranker([0.9, 0.1], delay=0.3), timeout_ms=50)
    service = _service(_config(rerank={"enabled": True}), store, reranker=reranker)
    try:
        result = service.retrieve("truy vấn")
    finally:
        service.close()
    assert result.rerank_fallback == "timeout"
    assert [chunk.child_id for chunk in result.chunks] == ["a", "b"]
    assert result.chunks[0].scores["rerank"] is None


def test_cache_hit_skips_second_retrieval() -> None:
    store = FakeStore(vector=[_record("a")])
    config = _config(cache={"enabled": True, "ttl_seconds": 60, "max_entries": 8})
    service = _service(config, store)
    try:
        first = service.retrieve("S3 là gì")
        second = service.retrieve("S3 là gì")
    finally:
        service.close()
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert store.vector_calls == 1


def test_decomposition_runs_parallel_subqueries() -> None:
    store = FakeStore(vector=[_record("a")])
    llm = FakeLLM({"subqueries": ["chi phí S3 Standard", "chi phí S3 Glacier"]})
    config = _config(
        decomposition={
            "enabled": True,
            "llm_enabled": True,
            "min_query_words": 5,
            "trigger_types": ["so_sanh", "nhieu_rang_buoc"],
        }
    )
    service = _service(config, store, llm=llm)
    try:
        result = service.retrieve("So sánh chi phí lưu trữ của S3 Standard và S3 Glacier")
    finally:
        service.close()
    assert result.decomposition_source == "llm"
    assert result.subqueries == ["chi phí S3 Standard", "chi phí S3 Glacier"]
    assert store.vector_calls == 2


def test_parent_chunks_are_deduplicated_per_section() -> None:
    store = FakeStore(
        vector=[
            _record("a", "p-shared", section="Mục 1"),
            _record("b", "p-shared", section="Mục 1"),
            _record("c", section="Mục 2"),
        ]
    )
    service = _service(_config(), store)
    try:
        result = service.retrieve("truy vấn")
    finally:
        service.close()
    assert [chunk.child_id for chunk in result.chunks] == ["a", "c"]
    assert store.parent_calls == [["p-shared", "p-c"]]


def test_comparison_adds_uncovered_documents() -> None:
    store = FakeStore(
        vector=[
            _record("a", document="EC2.pdf"),
            _record("b", document="EC2.pdf"),
            _record("c", document="S3.pdf"),
        ]
    )
    service = _service(_config(top_k={"adaptive": False, "default": 1, "min": 1}), store)
    try:
        result = service.retrieve("So sánh Amazon S3 và Amazon EBS")
    finally:
        service.close()
    assert [chunk.document for chunk in result.chunks] == ["EC2.pdf", "S3.pdf"]
    assert [chunk.rank for chunk in result.chunks] == [1, 2]


def test_explicit_top_k_skips_comparison_coverage() -> None:
    store = FakeStore(vector=[_record("a", document="EC2.pdf"), _record("c", document="S3.pdf")])
    service = _service(_config(top_k={"adaptive": False, "default": 1, "min": 1}), store)
    try:
        result = service.retrieve("So sánh Amazon S3 và Amazon EBS", top_k=1)
    finally:
        service.close()
    assert [chunk.document for chunk in result.chunks] == ["EC2.pdf"]


def test_empty_query_is_rejected() -> None:
    service = _service(_config(), FakeStore())
    try:
        with pytest.raises(ValueError):
            service.retrieve("   ")
    finally:
        service.close()


def test_invalid_top_k_is_rejected() -> None:
    service = _service(_config(), FakeStore(vector=[_record("a")]))
    try:
        with pytest.raises(ValueError):
            service.retrieve("truy vấn", top_k=0)
    finally:
        service.close()
