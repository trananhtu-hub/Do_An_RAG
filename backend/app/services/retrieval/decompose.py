from __future__ import annotations

import re

from .config import DecompositionConfig
from .llm import GeminiTextClient
from .text import normalize_query, word_count
from .types import DecompositionResult, QueryClassification

_SPLIT_PATTERNS = (
    re.compile(r"\s*;\s*"),
    re.compile(r"\s*\?\s*"),
    re.compile(r"\s+trong khi\s+", re.IGNORECASE),
    re.compile(r"\s+và\s+", re.IGNORECASE),
)

DECOMPOSE_PROMPT = """Bạn tách câu hỏi ôn thi AWS SAA-C03 thành tối đa {max_subqueries} truy vấn con
độc lập, giữ nguyên thuật ngữ chuyên môn và ràng buộc định lượng. Không thêm kiến thức mới.
Chỉ trả JSON dạng {{"subqueries": ["...", "..."]}}.
Câu hỏi: {query}"""


class QueryDecomposer:
    def __init__(
        self,
        config: DecompositionConfig,
        llm: GeminiTextClient | None = None,
    ) -> None:
        self._config = config
        self._llm = llm

    def should_decompose(self, query: str, classification: QueryClassification) -> bool:
        if not self._config.enabled:
            return False
        if classification.query_type not in self._config.trigger_types:
            return False
        return word_count(query) >= self._config.min_query_words

    def decompose(self, query: str, classification: QueryClassification) -> DecompositionResult:
        normalized = normalize_query(query)
        if not self.should_decompose(normalized, classification):
            return DecompositionResult([normalized], "single")
        if self._config.llm_enabled and self._llm is not None:
            subqueries = self._decompose_with_llm(normalized)
            if subqueries is not None:
                return DecompositionResult(subqueries, "llm")
        subqueries = self._decompose_heuristically(normalized)
        if len(subqueries) >= 2:
            return DecompositionResult(subqueries, "heuristic")
        return DecompositionResult([normalized], "single")

    def _decompose_with_llm(self, query: str) -> list[str] | None:
        if self._llm is None:
            return None
        try:
            data = self._llm.generate_json(
                self._config.llm_model,
                DECOMPOSE_PROMPT.format(max_subqueries=self._config.max_subqueries, query=query),
                self._config.llm_timeout_ms,
            )
        except Exception:  # noqa: BLE001 - mạng/quota đều quay về heuristic
            return None
        if not data or not isinstance(data.get("subqueries"), list):
            return None
        return self._sanitize([str(item) for item in data["subqueries"]], query)

    def _decompose_heuristically(self, query: str) -> list[str]:
        parts = [query]
        for pattern in _SPLIT_PATTERNS:
            next_parts: list[str] = []
            for part in parts:
                split = [segment.strip(" ,.") for segment in pattern.split(part)]
                if len(split) > 1 and all(word_count(segment) >= 4 for segment in split):
                    next_parts.extend(split)
                else:
                    next_parts.append(part)
            parts = next_parts
            if len(parts) >= self._config.max_subqueries:
                break
        return self._sanitize(parts, query) or []

    def _sanitize(self, candidates: list[str], original: str) -> list[str] | None:
        result: list[str] = []
        seen = {normalize_query(original).casefold()}
        for candidate in candidates:
            text = normalize_query(candidate)
            key = text.casefold()
            if not text or key in seen or word_count(text) < 3:
                continue
            seen.add(key)
            result.append(text)
            if len(result) >= self._config.max_subqueries:
                break
        return result if len(result) >= 2 else None
