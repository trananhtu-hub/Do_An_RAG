from __future__ import annotations

import json
import re

from pydantic import ValidationError

from .types import AnswerPayload

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class SchemaError(ValueError):
    """Đầu ra của mô hình không phải JSON đúng schema."""

    def __init__(self, message: str, *, raw: str) -> None:
        super().__init__(message)
        self.raw = raw


def extract_json_object(text: str) -> dict:
    cleaned = _FENCE.sub("", text.strip()).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            raise SchemaError("Không tìm thấy đối tượng JSON trong đầu ra", raw=text) from exc
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise SchemaError(f"JSON không hợp lệ: {exc}", raw=text) from exc
    if not isinstance(data, dict):
        raise SchemaError("Đầu ra JSON phải là một đối tượng", raw=text)
    return data


def parse_answer(text: str) -> AnswerPayload:
    data = extract_json_object(text)
    try:
        payload = AnswerPayload.model_validate(data)
    except ValidationError as exc:
        raise SchemaError(_format_validation_error(exc), raw=text) from exc
    return _normalize(payload)


def _normalize(payload: AnswerPayload) -> AnswerPayload:
    if payload.abstained and payload.abstention_type == "none":
        payload = payload.model_copy(update={"abstention_type": "unknown"})
    if not payload.abstained and payload.abstention_type != "none":
        payload = payload.model_copy(update={"abstention_type": "none"})
    return payload


def repair_message(error: SchemaError, payload_template: str) -> str:
    return (
        "Đầu ra trước không đúng schema JSON.\n"
        f"Lỗi: {error}\n"
        "Hãy trả lại DUY NHẤT một đối tượng JSON đúng schema sau, không thêm văn bản:\n"
        f"{payload_template}"
    )


def _format_validation_error(error: ValidationError) -> str:
    parts = []
    for item in error.errors()[:5]:
        location = ".".join(str(part) for part in item.get("loc", ()))
        parts.append(f"{location}: {item.get('msg', '')}")
    return "; ".join(parts) or "Dữ liệu không khớp schema"
