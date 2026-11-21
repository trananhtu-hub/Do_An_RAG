from __future__ import annotations

from app.services.retrieval.config import DecompositionConfig
from app.services.retrieval.decompose import QueryDecomposer
from app.services.retrieval.types import QueryClassification


class FakeLLM:
    def __init__(self, payload: dict[str, object] | None = None, error: Exception | None = None):
        self.payload = payload
        self.error = error

    def generate_json(self, model: str, prompt: str, timeout_ms: int) -> dict[str, object] | None:
        if self.error is not None:
            raise self.error
        return self.payload


def _classification(query_type: str = "so_sanh") -> QueryClassification:
    return QueryClassification(
        query_type=query_type, confidence=0.5, source="heuristic", k_min=4, k_max=8
    )


def _decomposer(llm: FakeLLM | None = None, **overrides: object) -> QueryDecomposer:
    base = DecompositionConfig(
        enabled=True,
        llm_enabled=llm is not None,
        max_subqueries=3,
        min_query_words=8,
        trigger_types=("so_sanh", "nhieu_rang_buoc"),
    )
    config = base
    for key, value in overrides.items():
        config = DecompositionConfig(**{**config.__dict__, key: value})
    return QueryDecomposer(config, llm)  # type: ignore[arg-type]


LONG_COMPARISON = (
    "So sánh chi phí lưu trữ giữa S3 Standard và S3 Glacier trong khi cần truy xuất thường xuyên"
)


def test_disabled_decomposition_returns_single_query() -> None:
    result = _decomposer(enabled=False).decompose(LONG_COMPARISON, _classification())
    assert result.subqueries == [LONG_COMPARISON]
    assert result.source == "single"


def test_short_query_is_not_decomposed() -> None:
    result = _decomposer(llm=FakeLLM({"subqueries": ["một", "hai"]})).decompose(
        "So sánh S3 và EBS", _classification()
    )
    assert result.source == "single"


def test_non_trigger_type_is_not_decomposed() -> None:
    result = _decomposer().decompose(LONG_COMPARISON, _classification("tra_cuu"))
    assert result.source == "single"


def test_llm_returns_subqueries() -> None:
    llm = FakeLLM({"subqueries": ["chi phí S3 Standard", "chi phí S3 Glacier"]})
    result = _decomposer(llm=llm).decompose(LONG_COMPARISON, _classification())
    assert result.source == "llm"
    assert result.subqueries == ["chi phí S3 Standard", "chi phí S3 Glacier"]


def test_llm_invalid_payload_falls_back_to_heuristic() -> None:
    llm = FakeLLM({"subqueries": "không phải danh sách"})
    result = _decomposer(llm=llm).decompose(LONG_COMPARISON, _classification())
    assert result.source == "heuristic"
    assert len(result.subqueries) >= 2


def test_heuristic_splits_long_comparison() -> None:
    result = _decomposer().decompose(LONG_COMPARISON, _classification())
    assert result.source == "heuristic"
    assert 2 <= len(result.subqueries) <= 3


def test_heuristic_without_separators_falls_back_to_single_query() -> None:
    query = "So sánh các phương án lưu trữ khối lượng lớn cho hệ thống phân tích dữ liệu"
    result = _decomposer().decompose(query, _classification())
    assert result.source == "single"
    assert result.subqueries == [query]


def test_max_subqueries_is_respected() -> None:
    llm = FakeLLM(
        {
            "subqueries": [
                "truy vấn một",
                "truy vấn hai",
                "truy vấn ba",
                "truy vấn bốn",
            ]
        }
    )
    result = _decomposer(llm=llm, max_subqueries=3).decompose(LONG_COMPARISON, _classification())
    assert len(result.subqueries) == 3


def test_duplicate_subqueries_are_removed() -> None:
    llm = FakeLLM({"subqueries": ["chi phí S3 Standard", "chi phí S3 Standard"]})
    result = _decomposer(llm=llm).decompose(LONG_COMPARISON, _classification())
    assert result.source == "heuristic"
