from __future__ import annotations

from .config import QUERY_TYPES, ClassifierConfig, TopKConfig
from .llm import DeepSeekTextClient
from .text import (
    extract_english_terms,
    normalize_query,
    strip_accents,
    word_count,
)
from .types import QueryClassification

COMPARISON_CUES = (
    "so sanh",
    "khac nhau",
    "khac biet",
    "khac gi",
    "versus",
    " vs ",
    "hay hon",
    "giong",
    "trong khi",
    "con lai",
    "uu diem",
    "nhuoc diem",
    "diem nao",
    "diem khac",
    "so voi",
    "khi nao nen dung",
    "nen dung cai nao",
    "lua chon nao",
    "manh hon",
)

CONSTRAINT_CUES = (
    "toi thieu",
    "toi da",
    "it nhat",
    "nhieu nhat",
    "bat buoc",
    "phai",
    "nen chon",
    "chi phi thap nhat",
    "reu nhat",
    "gioi han",
    "dong thoi",
    "dam bao",
    "chap nhan",
    "trong bao lau",
    "bao nhieu ngay",
    "chi phi",
    "rang buoc",
)

LOOKUP_CUES = (
    "la gi",
    "bao nhieu",
    "nhung nao",
    "dinh nghia",
    "gom nhung",
    "co nhung",
    "the nao",
    "khi nao",
    "o dau",
)

CLASSIFIER_PROMPT = """Bạn là bộ phân loại câu hỏi ôn thi AWS SAA-C03.
Phân loại câu hỏi vào đúng một nhãn:
- tra_cuu: hỏi một khái niệm/số liệu cụ thể.
- so_sanh: yêu cầu so sánh hai hay nhiều phương án/dịch vụ.
- nhieu_rang_buoc: tình huống có nhiều điều kiện ràng buộc cần thỏa đồng thời.
- tron_thuat_ngu: câu tiếng Việt trộn nhiều thuật ngữ tiếng Anh.
Chỉ trả JSON dạng {{"type": "<nhãn>"}}.
Câu hỏi: {query}"""


class QueryClassifier:
    def __init__(
        self,
        config: ClassifierConfig,
        top_k: TopKConfig,
        llm: DeepSeekTextClient | None = None,
    ) -> None:
        self._config = config
        self._top_k = top_k
        self._llm = llm

    def classify(self, query: str) -> QueryClassification:
        normalized = normalize_query(query)
        scores, evidence = self._heuristic_scores(normalized)
        best_type = max(scores, key=lambda name: scores[name])
        total = sum(scores.values()) or 1.0
        confidence = scores[best_type] / total
        source = "heuristic"
        if (
            self._config.llm_enabled
            and self._llm is not None
            and confidence < self._config.min_confidence
        ):
            llm_type = self._classify_with_llm(normalized)
            if llm_type is not None:
                best_type = llm_type
                confidence = max(confidence, self._config.min_confidence)
                source = "llm"
        k_min, k_max = self._top_k.type_ranges.get(best_type, (self._top_k.min, self._top_k.max))
        return QueryClassification(
            query_type=best_type,
            confidence=round(confidence, 3),
            source=source,
            k_min=max(k_min, self._top_k.min),
            k_max=min(k_max, self._top_k.max),
            evidence={key: round(value, 3) for key, value in evidence.items()},
        )

    def _heuristic_scores(self, query: str) -> tuple[dict[str, float], dict[str, float]]:
        plain = f" {strip_accents(query).casefold()} "
        words = word_count(query)
        english = extract_english_terms(query, 3, 12)
        comparison_hits = sum(1 for cue in COMPARISON_CUES if cue in plain)
        constraint_hits = sum(1 for cue in CONSTRAINT_CUES if cue in plain)
        lookup_hits = sum(1 for cue in LOOKUP_CUES if cue in plain)

        comparison = 2.0 * comparison_hits
        constraint = 1.4 * constraint_hits + (0.8 if words >= 28 else 0.0)
        english_terms = min(1.8, 0.6 * len(english))
        lookup = 0.6 + 0.5 * lookup_hits + (0.4 if words <= 18 else 0.0)

        scores = {
            "tra_cuu": max(0.1, lookup),
            "so_sanh": max(0.1, comparison),
            "nhieu_rang_buoc": max(0.1, constraint),
            "tron_thuat_ngu": max(0.1, english_terms),
        }
        # Chỉ giữ nhãn hợp lệ theo cấu hình.
        scores = {name: scores[name] for name in QUERY_TYPES}
        evidence = {
            "comparison_hits": comparison_hits,
            "constraint_hits": constraint_hits,
            "lookup_hits": lookup_hits,
            "english_terms": len(english),
            "words": words,
        }
        return scores, evidence

    def _classify_with_llm(self, query: str) -> str | None:
        if self._llm is None:
            return None
        try:
            data = self._llm.generate_json(
                self._config.llm_model,
                CLASSIFIER_PROMPT.format(query=query),
                self._config.llm_timeout_ms,
            )
        except Exception:  # noqa: BLE001 - mạng/quota đều quay về heuristic
            return None
        if not data:
            return None
        value = str(data.get("type", "")).strip()
        return value if value in QUERY_TYPES else None
