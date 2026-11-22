from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "retrieval.yaml"
QUERY_TYPES = ("tra_cuu", "so_sanh", "nhieu_rang_buoc", "tron_thuat_ngu")


def _section(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key) or {}
    if not isinstance(value, dict):
        raise ValueError(f"Mục cấu hình '{key}' phải là ánh xạ")
    return value


def _pair(raw: dict[str, Any], key: str, default: tuple[int, int]) -> tuple[int, int]:
    value = raw.get(key, default)
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise ValueError(f"'{key}' phải là cặp [min, max]")
    return int(value[0]), int(value[1])


@dataclass(frozen=True)
class SourceFilterConfig:
    enabled: bool = False
    exclude_kinds: tuple[str, ...] = ()
    bypass_patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class EmbeddingConfig:
    model: str = "gemini-embedding-001"
    dimensions: int = 768
    task_type: str = "RETRIEVAL_QUERY"
    timeout_ms: int = 8000
    max_retries: int = 2
    cache_size: int = 512


@dataclass(frozen=True)
class VectorConfig:
    enabled: bool = True
    weight: float = 1.0
    candidates: int = 50
    similarity_threshold: float = 0.5
    ef_search: int = 100


@dataclass(frozen=True)
class TrigramConfig:
    enabled: bool = True
    weight: float = 0.2
    candidates: int = 30
    min_matched_terms: int = 1
    min_term_length: int = 2
    max_terms: int = 8


@dataclass(frozen=True)
class LexicalConfig:
    enabled: bool = True
    weight: float = 0.3
    candidates: int = 50
    min_term_length: int = 2
    max_terms: int = 24
    trigram: TrigramConfig = field(default_factory=TrigramConfig)


@dataclass(frozen=True)
class FusionConfig:
    method: str = "rrf"
    k: int = 60
    candidates: int = 30


@dataclass(frozen=True)
class RerankConfig:
    enabled: bool = True
    model: str = "BAAI/bge-reranker-v2-m3"
    candidates: int = 30
    batch_size: int = 16
    max_length: int = 512
    timeout_ms: int = 3000
    device: str = "auto"
    precision: str = "fp16"
    warmup: bool = True
    content_scope: str = "child"
    context_header: bool = True
    source_filter: SourceFilterConfig = field(default_factory=SourceFilterConfig)


@dataclass(frozen=True)
class ClassifierConfig:
    llm_enabled: bool = True
    llm_model: str = "gemini-3.8-flash"
    llm_timeout_ms: int = 1500
    min_confidence: float = 0.6


@dataclass(frozen=True)
class TopKConfig:
    adaptive: bool = True
    default: int = 5
    min: int = 3
    max: int = 8
    token_budget: int = 6000
    relative_score_floor: float = 0.35
    type_ranges: dict[str, tuple[int, int]] = field(
        default_factory=lambda: {
            "tra_cuu": (3, 5),
            "so_sanh": (4, 8),
            "nhieu_rang_buoc": (5, 8),
            "tron_thuat_ngu": (4, 7),
        }
    )


@dataclass(frozen=True)
class DecompositionConfig:
    enabled: bool = True
    llm_enabled: bool = True
    llm_model: str = "gemini-3.8-flash"
    llm_timeout_ms: int = 2500
    max_subqueries: int = 3
    min_query_words: int = 18
    trigger_types: tuple[str, ...] = ("so_sanh", "nhieu_rang_buoc")


@dataclass(frozen=True)
class ParentChildConfig:
    expand_parent: bool = True


@dataclass(frozen=True)
class CacheConfig:
    enabled: bool = True
    ttl_seconds: int = 3600
    max_entries: int = 512


@dataclass(frozen=True)
class LatencyConfig:
    subquery_workers: int = 3


@dataclass(frozen=True)
class RetrievalConfig:
    version: int = 1
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    vector: VectorConfig = field(default_factory=VectorConfig)
    lexical: LexicalConfig = field(default_factory=LexicalConfig)
    fusion: FusionConfig = field(default_factory=FusionConfig)
    rerank: RerankConfig = field(default_factory=RerankConfig)
    classifier: ClassifierConfig = field(default_factory=ClassifierConfig)
    top_k: TopKConfig = field(default_factory=TopKConfig)
    decomposition: DecompositionConfig = field(default_factory=DecompositionConfig)
    parent_child: ParentChildConfig = field(default_factory=ParentChildConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    latency: LatencyConfig = field(default_factory=LatencyConfig)
    benchmark: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.fusion.method != "rrf":
            raise ValueError("Hiện chỉ hỗ trợ fusion.method = rrf")
        if self.fusion.k <= 0:
            raise ValueError("fusion.k phải lớn hơn 0")
        if self.vector.weight < 0 or self.lexical.weight < 0 or self.lexical.trigram.weight < 0:
            raise ValueError("Trọng số RRF không được âm")
        if not 0.0 <= self.vector.similarity_threshold <= 1.0:
            raise ValueError("vector.similarity_threshold phải trong [0, 1]")
        if self.lexical.trigram.min_matched_terms < 1:
            raise ValueError("lexical.trigram.min_matched_terms phải lớn hơn 0")
        if self.top_k.min < 1 or self.top_k.max < self.top_k.min:
            raise ValueError("top_k.min/top_k.max không hợp lệ")
        if not self.top_k.min <= self.top_k.default <= self.top_k.max:
            raise ValueError("top_k.default phải trong [top_k.min, top_k.max]")
        if self.top_k.token_budget <= 0:
            raise ValueError("top_k.token_budget phải lớn hơn 0")
        if self.cache.ttl_seconds <= 0 or self.cache.max_entries <= 0:
            raise ValueError("cache.ttl_seconds và cache.max_entries phải lớn hơn 0")
        if self.rerank.batch_size <= 0 or self.rerank.timeout_ms <= 0:
            raise ValueError("rerank.batch_size và rerank.timeout_ms phải lớn hơn 0")
        if self.rerank.content_scope not in ("child", "parent"):
            raise ValueError("rerank.content_scope phải là 'child' hoặc 'parent'")
        if self.rerank.source_filter.enabled and not self.rerank.source_filter.exclude_kinds:
            raise ValueError("rerank.source_filter.exclude_kinds không được rỗng khi bật")
        for pattern in self.rerank.source_filter.bypass_patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(
                    f"rerank.source_filter.bypass_patterns không hợp lệ: {pattern}"
                ) from exc
        for name, (low, high) in self.top_k.type_ranges.items():
            if name not in QUERY_TYPES:
                raise ValueError(f"Loại truy vấn không hợp lệ trong type_ranges: {name}")
            if low < 1 or high < low:
                raise ValueError(f"type_ranges[{name}] không hợp lệ")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RetrievalConfig:
        embedding = _section(raw, "embedding")
        vector = _section(raw, "vector")
        lexical = _section(raw, "lexical")
        trigram = _section(lexical, "trigram")
        fusion = _section(raw, "fusion")
        rerank = _section(raw, "rerank")
        source_filter = _section(rerank, "source_filter")
        classifier = _section(raw, "classifier")
        top_k = _section(raw, "top_k")
        decomposition = _section(raw, "decomposition")
        parent_child = _section(raw, "parent_child")
        cache = _section(raw, "cache")
        latency = _section(raw, "latency")
        type_ranges = top_k.get("type_ranges") or TopKConfig().type_ranges
        ranges = {str(name): _pair(type_ranges, name, (3, 8)) for name in type_ranges}
        return cls(
            version=int(raw.get("version", 1)),
            embedding=EmbeddingConfig(
                model=str(embedding.get("model", EmbeddingConfig.model)),
                dimensions=int(embedding.get("dimensions", EmbeddingConfig.dimensions)),
                task_type=str(embedding.get("task_type", EmbeddingConfig.task_type)),
                timeout_ms=int(embedding.get("timeout_ms", EmbeddingConfig.timeout_ms)),
                max_retries=int(embedding.get("max_retries", EmbeddingConfig.max_retries)),
                cache_size=int(embedding.get("cache_size", EmbeddingConfig.cache_size)),
            ),
            vector=VectorConfig(
                enabled=bool(vector.get("enabled", True)),
                weight=float(vector.get("weight", 1.0)),
                candidates=int(vector.get("candidates", 50)),
                similarity_threshold=float(vector.get("similarity_threshold", 0.5)),
                ef_search=int(vector.get("ef_search", 100)),
            ),
            lexical=LexicalConfig(
                enabled=bool(lexical.get("enabled", True)),
                weight=float(lexical.get("weight", 0.3)),
                candidates=int(lexical.get("candidates", 50)),
                min_term_length=int(lexical.get("min_term_length", 2)),
                max_terms=int(lexical.get("max_terms", 24)),
                trigram=TrigramConfig(
                    enabled=bool(trigram.get("enabled", True)),
                    weight=float(trigram.get("weight", 0.2)),
                    candidates=int(trigram.get("candidates", 30)),
                    min_matched_terms=int(trigram.get("min_matched_terms", 1)),
                    min_term_length=int(trigram.get("min_term_length", 2)),
                    max_terms=int(trigram.get("max_terms", 8)),
                ),
            ),
            fusion=FusionConfig(
                method=str(fusion.get("method", "rrf")),
                k=int(fusion.get("k", 60)),
                candidates=int(fusion.get("candidates", 30)),
            ),
            rerank=RerankConfig(
                enabled=bool(rerank.get("enabled", True)),
                model=str(rerank.get("model", RerankConfig.model)),
                candidates=int(rerank.get("candidates", 30)),
                batch_size=int(rerank.get("batch_size", 16)),
                max_length=int(rerank.get("max_length", 512)),
                timeout_ms=int(rerank.get("timeout_ms", 3000)),
                device=str(rerank.get("device", "auto")),
                precision=str(rerank.get("precision", "fp16")),
                warmup=bool(rerank.get("warmup", True)),
                content_scope=str(rerank.get("content_scope", "child")),
                context_header=bool(rerank.get("context_header", True)),
                source_filter=SourceFilterConfig(
                    enabled=bool(source_filter.get("enabled", False)),
                    exclude_kinds=tuple(
                        str(kind) for kind in source_filter.get("exclude_kinds", ())
                    ),
                    bypass_patterns=tuple(
                        str(pattern) for pattern in source_filter.get("bypass_patterns", ())
                    ),
                ),
            ),
            classifier=ClassifierConfig(
                llm_enabled=bool(classifier.get("llm_enabled", True)),
                llm_model=str(classifier.get("llm_model", "gemini-3.8-flash")),
                llm_timeout_ms=int(classifier.get("llm_timeout_ms", 1500)),
                min_confidence=float(classifier.get("min_confidence", 0.6)),
            ),
            top_k=TopKConfig(
                adaptive=bool(top_k.get("adaptive", True)),
                default=int(top_k.get("default", 5)),
                min=int(top_k.get("min", 3)),
                max=int(top_k.get("max", 8)),
                token_budget=int(top_k.get("token_budget", 6000)),
                relative_score_floor=float(top_k.get("relative_score_floor", 0.35)),
                type_ranges=ranges,
            ),
            decomposition=DecompositionConfig(
                enabled=bool(decomposition.get("enabled", True)),
                llm_enabled=bool(decomposition.get("llm_enabled", True)),
                llm_model=str(decomposition.get("llm_model", "gemini-3.8-flash")),
                llm_timeout_ms=int(decomposition.get("llm_timeout_ms", 2500)),
                max_subqueries=int(decomposition.get("max_subqueries", 3)),
                min_query_words=int(decomposition.get("min_query_words", 18)),
                trigger_types=tuple(decomposition.get("trigger_types", ())),
            ),
            parent_child=ParentChildConfig(
                expand_parent=bool(parent_child.get("expand_parent", True))
            ),
            cache=CacheConfig(
                enabled=bool(cache.get("enabled", True)),
                ttl_seconds=int(cache.get("ttl_seconds", 3600)),
                max_entries=int(cache.get("max_entries", 512)),
            ),
            latency=LatencyConfig(
                subquery_workers=int(latency.get("subquery_workers", 3)),
            ),
            benchmark=dict(raw.get("benchmark") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        ranges = data["top_k"]["type_ranges"]
        data["top_k"]["type_ranges"] = {name: list(pair) for name, pair in ranges.items()}
        data["decomposition"]["trigger_types"] = list(self.decomposition.trigger_types)
        return data

    def fingerprint(self) -> str:
        data = self.to_dict()
        data.pop("benchmark", None)
        payload = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def with_overrides(self, overrides: dict[str, Any]) -> RetrievalConfig:
        merged = _deep_merge(self.to_dict(), overrides)
        return RetrievalConfig.from_dict(merged)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path | None = None) -> RetrievalConfig:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp cấu hình: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("Tệp cấu hình phải chứa một ánh xạ YAML")
    return RetrievalConfig.from_dict(raw)
