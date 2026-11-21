from __future__ import annotations

import pytest
from app.services.generation.config import GenerationConfig
from app.services.generation.providers import FallbackChain
from app.services.generation.service import GenerationService
from conftest import FakeProvider, answer_json, make_chunk


def _service(texts: list[str], **config_overrides) -> tuple[GenerationService, FakeProvider]:
    config = GenerationConfig.from_dict({"prompt_version": "v1", **config_overrides})
    provider = FakeProvider(texts)
    service = GenerationService(config, FallbackChain([provider]))
    return service, provider


def test_answers_with_citations_and_cost() -> None:
    service, provider = _service([answer_json()])
    result = service.answer("S3 Standard dùng khi nào?", chunks=[make_chunk()])
    assert result.payload.abstained is False
    assert result.citation_report.ok
    assert result.citation_report.citation_validity == 1.0
    assert result.provider == "fake"
    assert result.usage_input_tokens == 100
    assert result.cost_usd == pytest.approx(0.0001)
    assert result.schema_retries == 0
    assert len(provider.calls) == 1


def test_system_message_has_no_whole_document_dump() -> None:
    service, provider = _service([answer_json()])
    service.answer("hỏi", chunks=[make_chunk(content="Nội dung ngắn")])
    system = provider.calls[0][0].content
    user = provider.calls[0][1].content
    assert "Nội dung ngắn" in user
    assert "Nội dung ngắn" not in system


def test_schema_retry_once_then_success() -> None:
    service, provider = _service(["không phải JSON", answer_json()])
    result = service.answer("hỏi", chunks=[make_chunk()])
    assert result.schema_retries == 1
    assert len(provider.calls) == 2
    repair = provider.calls[1]
    assert len(repair) == 4
    assert repair[2].role == "assistant"
    assert "schema" in repair[3].content.lower()
    assert result.usage_input_tokens == 200


def test_schema_failure_after_retry_raises() -> None:
    from app.services.generation.schema import SchemaError

    service, provider = _service(["sai", "vẫn sai"])
    with pytest.raises(SchemaError):
        service.answer("hỏi", chunks=[make_chunk()])
    assert len(provider.calls) == 2


def test_schema_retries_zero_means_single_call() -> None:
    from app.services.generation.schema import SchemaError

    service, provider = _service(["sai"], schema_retries=0)
    with pytest.raises(SchemaError):
        service.answer("hỏi", chunks=[make_chunk()])
    assert len(provider.calls) == 1


def test_abstention_clamps_confidence_and_clears_citations() -> None:
    payload = answer_json(
        answer="Tài liệu hiện có chưa đề cập đến Amazon Bedrock.",
        abstained=True,
        abstention_type="out_of_scope",
        confidence=0.95,
    )
    service, _ = _service([payload])
    result = service.answer("Bedrock là gì?", chunks=[make_chunk()])
    assert result.payload.abstained is True
    assert result.payload.abstention_type == "out_of_scope"
    assert result.payload.confidence == 0.2
    assert result.payload.citations == []
    assert result.citation_report.citation_validity == 1.0


def test_missing_citation_produces_warning() -> None:
    service, _ = _service([answer_json(answer="S3 Standard dùng cho dữ liệu nóng.", citations=[])])
    result = service.answer("hỏi", chunks=[make_chunk()])
    assert any("không có trích dẫn" in warning for warning in result.warnings)


def test_invalid_citation_produces_warning() -> None:
    service, _ = _service([answer_json(answer="Sai nguồn [S3 Storage Classes – Mục Không Có].")])
    result = service.answer("hỏi", chunks=[make_chunk()])
    assert result.citation_report.citation_validity == 0.0
    assert any("không khớp ngữ cảnh" in warning for warning in result.warnings)


def test_low_confidence_produces_warning() -> None:
    service, _ = _service([answer_json(confidence=0.2)])
    result = service.answer("hỏi", chunks=[make_chunk()])
    assert any("Độ tin cậy" in warning for warning in result.warnings)


def test_empty_context_abstains_without_calling_model() -> None:
    service, provider = _service([answer_json()])
    result = service.answer("hỏi", chunks=[])
    assert result.payload.abstained is True
    assert result.payload.abstention_type == "no_evidence"
    assert result.provider == "none"
    assert provider.calls == []
    assert result.latency_ms >= 0


def test_mode_selected_from_query_type() -> None:
    from app.services.retrieval.types import RetrievalResult

    service, provider = _service([answer_json()])
    retrieval = RetrievalResult(
        query="q",
        normalized_query="q",
        query_type="nhieu_rang_buoc",
        classification_source="rule",
        classification_confidence=0.9,
        subqueries=[],
        decomposition_source="none",
        chunks=[],
        k=5,
        timings_ms={},
    )
    result = service.answer("q", chunks=[make_chunk()], retrieval_result=retrieval)
    assert result.prompt_mode == "multi_constraint"
    assert "Bảng kiểm ràng buộc" in provider.calls[0][0].content


def test_fallback_metadata_survives() -> None:
    from app.services.generation.providers import LLMError, LLMResponse

    class Failing:
        name = "primary"
        model = "m"

        def complete(self, messages, **kwargs):
            raise LLMError("hỏng", provider="primary")

        def close(self) -> None:
            pass

    class Working:
        name = "backup"
        model = "m"

        def complete(self, messages, **kwargs):
            return LLMResponse(text=answer_json(), model="m", provider="backup")

        def close(self) -> None:
            pass

    config = GenerationConfig.from_dict({"prompt_version": "v1"})
    service = GenerationService(config, FallbackChain([Failing(), Working()]))
    result = service.answer("hỏi", chunks=[make_chunk()])
    assert result.fallback_used == "backup"
    assert result.attempts == ("primary", "backup")


def test_log_writer_called_once() -> None:
    class FakeWriter:
        def __init__(self) -> None:
            self.calls: list = []

        def write(self, result, *, session_id=None, rewritten_query=None) -> bool:
            self.calls.append((result, session_id, rewritten_query))
            return True

    config = GenerationConfig.from_dict({"prompt_version": "v1"})
    writer = FakeWriter()
    service = GenerationService(
        config, FallbackChain([FakeProvider([answer_json()])]), log_writer=writer
    )
    result = service.answer("hỏi", chunks=[make_chunk()], session_id=None)
    assert len(writer.calls) == 1
    assert writer.calls[0][0] is result


def test_invalid_prompt_mode_rejected() -> None:
    service, _ = _service([answer_json()])
    with pytest.raises(ValueError, match="mode"):
        service.answer("hỏi", chunks=[make_chunk()], mode="khong_co")
