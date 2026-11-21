from __future__ import annotations

from app.services.retrieval.classify import QueryClassifier
from app.services.retrieval.config import ClassifierConfig, TopKConfig


class FakeLLM:
    def __init__(self, payload: dict[str, object] | None = None, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.calls: list[tuple[str, str, int]] = []

    def generate_json(self, model: str, prompt: str, timeout_ms: int) -> dict[str, object] | None:
        self.calls.append((model, prompt, timeout_ms))
        if self.error is not None:
            raise self.error
        return self.payload


def _classifier(llm: FakeLLM | None = None, *, llm_enabled: bool = False) -> QueryClassifier:
    return QueryClassifier(
        ClassifierConfig(llm_enabled=llm_enabled, min_confidence=0.6),
        TopKConfig(),
        llm,  # type: ignore[arg-type]
    )


def test_heuristic_detects_comparison_question() -> None:
    result = _classifier().classify("So sánh Multi-AZ và Read Replica cho RDS")
    assert result.query_type == "so_sanh"
    assert result.source == "heuristic"
    assert result.k_min <= result.k_max


def test_heuristic_detects_lookup_question() -> None:
    result = _classifier().classify("Amazon S3 là gì?")
    assert result.query_type == "tra_cuu"


def test_heuristic_detects_multi_constraint_question() -> None:
    result = _classifier().classify(
        "Cần chọn dịch vụ lưu trữ 90 ngày với chi phí thấp nhất và phải bền vững"
    )
    assert result.query_type == "nhieu_rang_buoc"


def test_heuristic_detects_english_term_mix() -> None:
    result = _classifier().classify("S3 Glacier Deep Archive khác S3 Standard ở điểm nào?")
    assert result.query_type == "tron_thuat_ngu"


def test_low_confidence_calls_llm_and_uses_its_label() -> None:
    llm = FakeLLM({"type": "so_sanh"})
    result = _classifier(llm, llm_enabled=True).classify("So sánh chi phí")
    assert result.query_type == "so_sanh"
    assert result.source == "llm"
    assert len(llm.calls) == 1


def test_llm_error_falls_back_to_heuristic() -> None:
    llm = FakeLLM(error=RuntimeError("mất mạng"))
    result = _classifier(llm, llm_enabled=True).classify("So sánh chi phí")
    assert result.source == "heuristic"


def test_llm_invalid_label_falls_back_to_heuristic() -> None:
    llm = FakeLLM({"type": "khong_hop_le"})
    result = _classifier(llm, llm_enabled=True).classify("So sánh chi phí")
    assert result.source == "heuristic"


def test_high_confidence_does_not_call_llm() -> None:
    llm = FakeLLM({"type": "so_sanh"})
    result = _classifier(llm, llm_enabled=True).classify("Amazon S3 là gì?")
    assert result.query_type == "tra_cuu"
    assert llm.calls == []
