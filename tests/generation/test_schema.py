from __future__ import annotations

import pytest
from app.services.generation.schema import SchemaError, parse_answer, repair_message
from conftest import answer_json


def test_parses_plain_json() -> None:
    payload = parse_answer(answer_json())
    assert payload.abstained is False
    assert payload.confidence == 0.9
    assert payload.citations[0].source == "S3 Storage Classes – S3 Standard"
    assert payload.reasoning_steps[0].buoc == 1


def test_strips_markdown_fence() -> None:
    payload = parse_answer(f"```json\n{answer_json()}\n```")
    assert payload.answer.startswith("S3 Standard")


def test_extracts_object_from_surrounding_text() -> None:
    payload = parse_answer(f"Đây là kết quả:\n{answer_json()}\nHết.")
    assert payload.citations


def test_confidence_percent_and_string_coerced() -> None:
    payload = parse_answer(answer_json(confidence="85"))
    assert payload.confidence == 0.85


def test_missing_answer_is_schema_error() -> None:
    with pytest.raises(SchemaError, match="answer"):
        parse_answer('{"confidence": 0.5}')


def test_non_json_is_schema_error() -> None:
    with pytest.raises(SchemaError, match="JSON"):
        parse_answer("Tôi không biết")


def test_steps_from_strings_are_repaired() -> None:
    payload = parse_answer(answer_json(reasoning_steps=["Bước một", "Bước hai"]))
    assert [step.noi_dung for step in payload.reasoning_steps] == ["Bước một", "Bước hai"]


def test_abstained_without_type_is_normalized() -> None:
    payload = parse_answer(answer_json(abstained=True, abstention_type="none", citations=[]))
    assert payload.abstention_type == "unknown"


def test_repair_message_mentions_error() -> None:
    error = SchemaError("answer: Field required", raw="")
    message = repair_message(error, "{}")
    assert "answer: Field required" in message
    assert "JSON" in message
