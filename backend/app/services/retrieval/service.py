from __future__ import annotations

import hashlib
import re
import threading
import time
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol

from .cache import TTLCache
from .classify import QueryClassifier
from .config import RetrievalConfig
from .decompose import QueryDecomposer
from .embedder import GeminiQueryEmbedder, QueryEmbedder
from .fusion import RankedList, rrf_fuse
from .llm import DEFAULT_BASE_URL, DeepSeekTextClient
from .rerank import CrossEncoderReranker, TimeoutReranker
from .store import PgChunkStore
from .text import (
    build_tsquery,
    extract_english_terms,
    extract_lexical_terms,
    normalize_query,
)
from .topk import select_top_k
from .types import ChunkRecord, RetrievalResult, RetrievedChunk


class ChunkStore(Protocol):
    def vector_search(
        self,
        vector: Sequence[float],
        limit: int,
        threshold: float,
        exclude_kinds: Sequence[str] = (),
    ) -> list[ChunkRecord]: ...

    def lexical_search(
        self, tsquery: str, limit: int, exclude_kinds: Sequence[str] = ()
    ) -> list[ChunkRecord]: ...

    def trigram_search(
        self,
        terms: Sequence[str],
        limit: int,
        min_matched_terms: int,
        exclude_kinds: Sequence[str] = (),
    ) -> list[ChunkRecord]: ...

    def fetch_parents(self, parent_ids: Sequence[str]) -> dict[str, str]: ...


def _ms(value: float) -> float:
    return round(value, 2)


def _dedupe_results(records: Sequence[ChunkRecord]) -> list[ChunkRecord]:
    """Mỗi mục con chỉ giữ một kết quả; không có mục thì theo chunk cha."""
    seen: set[tuple[str, str]] = set()
    unique: list[ChunkRecord] = []
    for record in records:
        key = (record.document, record.section or record.parent_id or record.child_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


class RetrievalService:
    """Tầng truy hồi lai: vector + full-text + RRF + rerank + top-k thích ứng."""

    def __init__(
        self,
        config: RetrievalConfig,
        store: ChunkStore,
        embedder: QueryEmbedder,
        *,
        reranker: TimeoutReranker | None = None,
        classifier: QueryClassifier | None = None,
        decomposer: QueryDecomposer | None = None,
        llm: DeepSeekTextClient | None = None,
        cache: TTLCache[RetrievalResult] | None = None,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self.config = config
        self._store = store
        self._embedder = embedder
        self._llm = llm
        self._classifier = classifier or QueryClassifier(config.classifier, config.top_k, llm)
        self._decomposer = decomposer or QueryDecomposer(config.decomposition, llm)
        self._reranker = reranker
        self._excluded_kinds = frozenset(config.rerank.source_filter.exclude_kinds)
        self._bypass_patterns = tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in config.rerank.source_filter.bypass_patterns
        )
        if self._reranker is None and config.rerank.enabled:
            base = CrossEncoderReranker(
                config.rerank.model,
                batch_size=config.rerank.batch_size,
                max_length=config.rerank.max_length,
                device=config.rerank.device,
                precision=config.rerank.precision,
            )
            self._reranker = TimeoutReranker(base, config.rerank.timeout_ms)
        if self._reranker is not None and config.rerank.warmup:
            self._reranker.warmup()
        if cache is not None:
            self._cache: TTLCache[RetrievalResult] | None = cache
        elif config.cache.enabled:
            self._cache = TTLCache(config.cache.ttl_seconds, config.cache.max_entries)
        else:
            self._cache = None
        workers = max(3, config.latency.subquery_workers * 3)
        self._workers = workers
        self._owns_executor = executor is None
        self._executor = executor or ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="retrieval"
        )
        self._warm_store_connections()

    def close(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
        if self._reranker is not None:
            self._reranker.close()
        close_store = getattr(self._store, "close", None)
        if callable(close_store):
            close_store()
        close_embedder = getattr(self._embedder, "close", None)
        if callable(close_embedder):
            close_embedder()
        if self._llm is not None:
            self._llm.close()

    def _warm_store_connections(self) -> None:
        """Mở sẵn kết nối cho mọi luồng để lượt truy vấn đầu không chịu phí bắt tay."""
        healthcheck = getattr(self._store, "healthcheck", None)
        if not callable(healthcheck):
            return
        futures = [self._executor.submit(healthcheck) for _ in range(self._workers)]
        for future in futures:
            try:
                future.result(timeout=20)
            except Exception:  # pragma: no cover - làm nóng thất bại không chặn dịch vụ
                pass

    def _cache_key(self, query: str, top_k: int | None) -> str:
        payload = f"{self.config.fingerprint()}|{query.casefold()}|{top_k}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def retrieve(self, query: str, top_k: int | None = None) -> RetrievalResult:
        started = time.perf_counter()
        normalized = normalize_query(query)
        if not normalized:
            raise ValueError("Truy vấn rỗng")
        if top_k is not None and top_k <= 0:
            raise ValueError("top_k phải lớn hơn 0")
        cache_key = self._cache_key(normalized, top_k)
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                timings = dict(cached.timings_ms)
                timings["total_ms"] = _ms((time.perf_counter() - started) * 1000)
                return replace(cached, cache_hit=True, timings_ms=timings)

        classification, classify_ms = self._timed(self._classifier.classify, normalized)
        decomposition, decompose_ms = self._timed(
            self._decomposer.decompose, normalized, classification
        )
        subqueries = decomposition.subqueries
        vectors, embed_ms = self._timed(self._embedder.embed_queries, subqueries)

        search_started = time.perf_counter()
        exclude_kinds = (
            tuple(self._excluded_kinds) if self._source_filter_applies(normalized) else ()
        )
        branch_records, branch_timings = self._search_branches(subqueries, vectors, exclude_kinds)
        search_ms = (time.perf_counter() - search_started) * 1000

        fusion_started = time.perf_counter()
        ranked_lists: list[RankedList] = []
        for label in ("vector", "lexical", "trigram"):
            records = branch_records.get(label)
            if not records:
                continue
            weight = {
                "vector": self.config.vector.weight,
                "lexical": self.config.lexical.weight,
                "trigram": self.config.lexical.trigram.weight,
            }[label]
            ranked_lists.append(RankedList(label, records, weight))
        fused = rrf_fuse(ranked_lists, self.config.fusion.k, self.config.fusion.candidates)
        # Loại chunk ngân hàng câu hỏi trước khi hợp nhất để chúng không chiếm chỗ của
        # chunk lý thuyết trong top-k; chỉ giữ câu hỏi khi không còn chunk lý thuyết nào.
        if self._source_filter_applies(normalized):
            theory = [
                record
                for record in fused
                if str(record.metadata.get("kind") or "") not in self._excluded_kinds
            ]
            if theory:
                fused = theory
        fusion_ms = (time.perf_counter() - fusion_started) * 1000

        rerank_ms = 0.0
        parent_ms = 0.0
        fallback: str | None = None
        if self.config.rerank.enabled and self._reranker is not None and fused:
            pool = fused[: min(self.config.rerank.candidates, len(fused))]
            if self._source_filter_applies(normalized):
                filtered = [
                    record
                    for record in pool
                    if str(record.metadata.get("kind") or "") not in self._excluded_kinds
                ]
                if filtered:
                    pool = filtered
            if self.config.rerank.content_scope == "parent":
                parent_started = time.perf_counter()
                self._load_parent_contents(pool)
                parent_ms += (time.perf_counter() - parent_started) * 1000
            texts = [self._rerank_text(record) for record in pool]
            attempt = self._reranker.score(normalized, texts)
            rerank_ms = attempt.elapsed_ms
            if attempt.scores is not None:
                order = sorted(range(len(pool)), key=lambda index: (-attempt.scores[index], index))
                pool = [pool[index] for index in order]
                for record, index in zip(pool, order, strict=True):
                    record.rerank_score = attempt.scores[index]
                    record.final_score = attempt.scores[index]
            else:
                fallback = attempt.error
                for record in pool:
                    record.final_score = record.rrf_score
            # Các chunk con của cùng một mục là những phần khác nhau của mục; giữ lại
            # tất cả cho tới khi rerank chọn ra phần khớp câu hỏi nhất, rồi mới gộp mục.
            fused = _dedupe_results(pool)
        else:
            fused = _dedupe_results(fused)
            for record in fused:
                record.final_score = record.rrf_score

        select_started = time.perf_counter()
        selected = select_top_k(fused, classification, self.config.top_k, override=top_k)
        if top_k is None and classification.query_type == "so_sanh" and selected:
            selected = self._ensure_compare_coverage(selected, fused, classification.k_max)
        if self.config.parent_child.expand_parent and selected:
            selected = _dedupe_results(selected)
            for rank, record in enumerate(selected, start=1):
                record.rank = rank
        select_ms = (time.perf_counter() - select_started) * 1000
        if self.config.parent_child.expand_parent and selected:
            parent_started = time.perf_counter()
            self._load_parent_contents(selected)
            parent_ms += (time.perf_counter() - parent_started) * 1000

        chunks = [self._to_retrieved(record) for record in selected]
        timings = {
            "classify_ms": _ms(classify_ms),
            "decompose_ms": _ms(decompose_ms),
            "embed_ms": _ms(embed_ms),
            "search_ms": _ms(search_ms),
            "vector_ms": _ms(branch_timings.get("vector", 0.0)),
            "lexical_ms": _ms(branch_timings.get("lexical", 0.0)),
            "trigram_ms": _ms(branch_timings.get("trigram", 0.0)),
            "fusion_ms": _ms(fusion_ms),
            "parent_ms": _ms(parent_ms),
            "rerank_ms": _ms(rerank_ms),
            "select_ms": _ms(select_ms),
            "total_ms": _ms((time.perf_counter() - started) * 1000),
        }
        result = RetrievalResult(
            query=query,
            normalized_query=normalized,
            query_type=classification.query_type,
            classification_source=classification.source,
            classification_confidence=classification.confidence,
            subqueries=subqueries,
            decomposition_source=decomposition.source,
            chunks=chunks,
            k=len(chunks),
            timings_ms=timings,
            rerank_fallback=fallback,
        )
        if self._cache is not None and fallback is None:
            self._cache.set(cache_key, result)
        return result

    def _search_branches(
        self,
        subqueries: list[str],
        vectors: list[list[float]],
        exclude_kinds: tuple[str, ...] = (),
    ) -> tuple[dict[str, list[ChunkRecord]], dict[str, float]]:
        tasks: list[tuple[str, int, Future[tuple[list[ChunkRecord], float]]]] = []
        lexical_cfg = self.config.lexical
        trigram_cfg = lexical_cfg.trigram
        for index, (query, vector) in enumerate(zip(subqueries, vectors, strict=True)):
            if self.config.vector.enabled:
                tasks.append(
                    (
                        "vector",
                        index,
                        self._executor.submit(
                            self._timed,
                            self._store.vector_search,
                            vector,
                            self.config.vector.candidates,
                            self.config.vector.similarity_threshold,
                            exclude_kinds,
                        ),
                    )
                )
            if lexical_cfg.enabled:
                terms_list = extract_lexical_terms(
                    query, lexical_cfg.min_term_length, lexical_cfg.max_terms
                )
                tsquery = build_tsquery(terms_list)
                if tsquery:
                    tasks.append(
                        (
                            "lexical",
                            index,
                            self._executor.submit(
                                self._timed,
                                self._store.lexical_search,
                                tsquery,
                                lexical_cfg.candidates,
                                exclude_kinds,
                            ),
                        )
                    )
                if trigram_cfg.enabled:
                    english = extract_english_terms(
                        query, trigram_cfg.min_term_length, trigram_cfg.max_terms
                    )
                    if english:
                        tasks.append(
                            (
                                "trigram",
                                index,
                                self._executor.submit(
                                    self._timed,
                                    self._store.trigram_search,
                                    english,
                                    trigram_cfg.candidates,
                                    trigram_cfg.min_matched_terms,
                                    exclude_kinds,
                                ),
                            )
                        )
        branches: dict[str, list[ChunkRecord]] = {"vector": [], "lexical": [], "trigram": []}
        timings: dict[str, float] = {"vector": 0.0, "lexical": 0.0, "trigram": 0.0}
        for label, _index, future in tasks:
            records, elapsed = future.result()
            branches[label].extend(records)
            timings[label] = max(timings[label], elapsed)
        return branches, timings

    def _timed(self, function: Any, *args: Any) -> tuple[Any, float]:
        started = time.perf_counter()
        value = function(*args)
        return value, (time.perf_counter() - started) * 1000

    def _ensure_compare_coverage(
        self,
        selected: list[ChunkRecord],
        pool: Sequence[ChunkRecord],
        k_max: int,
    ) -> list[ChunkRecord]:
        """Câu so sánh cần mỗi tài liệu liên quan có mặt; bù tài liệu chưa được đại diện."""
        scores = [record.final_score for record in selected if record.final_score is not None]
        if not scores or max(scores) <= 0:
            return selected
        # Chỉ bù tài liệu có điểm không thấp hơn hẳn mức thấp nhất đã chọn, tránh kéo
        # tài liệu không liên quan (điểm sát 0) vào ngữ cảnh.
        gate = min(scores) * 0.25
        covered = {record.document for record in selected}
        extra: list[ChunkRecord] = []
        for record in pool:
            if len(selected) + len(extra) >= k_max:
                break
            if record.document in covered:
                continue
            if float(record.final_score or 0.0) < gate:
                continue
            covered.add(record.document)
            extra.append(record)
        if not extra:
            return selected
        merged = _dedupe_results([*selected, *extra])
        for rank, record in enumerate(merged, start=1):
            record.rank = rank
        return merged

    def _source_filter_applies(self, query: str) -> bool:
        config = self.config.rerank.source_filter
        if not config.enabled or not self._excluded_kinds:
            return False
        return not any(pattern.search(query) for pattern in self._bypass_patterns)

    def _load_parent_contents(self, records: Sequence[ChunkRecord]) -> None:
        missing = [
            record.parent_id
            for record in records
            if record.parent_id and record.parent_content is None
        ]
        if not missing:
            return
        parents = self._store.fetch_parents(list(dict.fromkeys(missing)))
        for record in records:
            if record.parent_content is None:
                record.parent_content = parents.get(record.parent_id or "")

    def _rerank_text(self, record: ChunkRecord) -> str:
        config = self.config.rerank
        content = record.content
        if config.content_scope == "parent" and record.parent_content:
            content = record.parent_content
        if not config.context_header:
            return content
        header = record.document
        if record.section:
            header = f"{header} - {record.section}" if header else record.section
        if record.heading:
            header = f"{header}. {record.heading}" if header else record.heading
        return f"{header}\n{content}" if header else content

    def _to_retrieved(self, record: ChunkRecord) -> RetrievedChunk:
        expand = self.config.parent_child.expand_parent and bool(record.parent_content)
        return RetrievedChunk(
            rank=record.rank or 0,
            child_id=record.child_id,
            parent_id=record.parent_id,
            content=record.context_content if expand else record.content,
            child_content=record.content,
            document=record.document,
            section=record.section,
            heading=record.heading,
            page=record.page,
            score=float(record.final_score or 0.0),
            scores={
                "vector": record.vector_score,
                "lexical": record.lexical_score,
                "trigram": record.trigram_score,
                "rrf": record.rrf_score,
                "rerank": record.rerank_score,
            },
            document_title=_document_title(record),
        )


def _document_title(record: ChunkRecord) -> str | None:
    title = record.metadata.get("document_title")
    return str(title) if title else None


_service: RetrievalService | None = None
_service_lock = threading.Lock()


def build_default_service(config_path: str | Path | None = None) -> RetrievalService:
    from .config import load_config
    from .settings import load_environment

    env = load_environment()
    config = load_config(config_path)
    database_url = env.get("DATABASE_URL", "")
    gemini_key = env.get("GEMINI_API_KEY", "")
    if not database_url:
        raise RuntimeError("Thiếu DATABASE_URL trong .env")
    if not gemini_key:
        raise RuntimeError("Thiếu GEMINI_API_KEY trong .env (chỉ dùng cho embedding)")
    store = PgChunkStore(database_url, ef_search=config.vector.ef_search)
    embedder = GeminiQueryEmbedder(
        gemini_key,
        model=config.embedding.model,
        dimensions=config.embedding.dimensions,
        task_type=config.embedding.task_type,
        timeout_ms=config.embedding.timeout_ms,
        max_retries=config.embedding.max_retries,
        cache_size=config.embedding.cache_size,
    )
    deepseek_key = env.get("DEEPSEEK_API_KEY") or env.get("OPENAI_API_KEY", "")
    llm = (
        DeepSeekTextClient(
            deepseek_key,
            base_url=env.get("DEEPSEEK_BASE_URL") or DEFAULT_BASE_URL,
        )
        if deepseek_key
        else None
    )
    return RetrievalService(config, store, embedder, llm=llm)


def get_service(config_path: str | Path | None = None) -> RetrievalService:
    global _service
    with _service_lock:
        if _service is None:
            _service = build_default_service(config_path)
    return _service


def reset_service() -> None:
    global _service
    with _service_lock:
        service, _service = _service, None
    if service is not None:
        service.close()


def retrieve(query: str, top_k: int | None = None) -> RetrievalResult:
    """API ổn định cho Giai đoạn 3 trở đi."""
    return get_service().retrieve(query, top_k=top_k)
