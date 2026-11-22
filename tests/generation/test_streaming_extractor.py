from __future__ import annotations

import json

from app.services.generation.streaming import AnswerStreamExtractor


def _feed_all(extractor: AnswerStreamExtractor, chunks: list[str]) -> str:
    return "".join(extractor.feed(chunk) for chunk in chunks)


def test_extracts_answer_from_one_chunk() -> None:
    extractor = AnswerStreamExtractor()
    payload = json.dumps({"answer": "S3 lưu trữ đối tượng.", "confidence": 0.9})
    assert extractor.feed(payload) == "S3 lưu trữ đối tượng."
    assert extractor.answer == "S3 lưu trữ đối tượng."
    assert extractor.finished


def test_extracts_answer_when_fed_character_by_character() -> None:
    extractor = AnswerStreamExtractor()
    payload = json.dumps({"answer": "Dòng một.\nDòng hai.", "citations": []})
    assert _feed_all(extractor, list(payload)) == "Dòng một.\nDòng hai."


def test_extracts_answer_from_provider_style_deltas() -> None:
    extractor = AnswerStreamExtractor()
    # Kiểu chia chunk thực tế của endpoint tương thích OpenAI: khóa và dấu hai chấm
    # nằm chung một delta, dấu nháy mở chuỗi giá trị nằm ở cuối delta đó.
    chunks = ['{"', "answer", '":"', "S", "3", ' là dịch vụ lưu trữ."', ', "confidence": 0.7}']
    assert _feed_all(extractor, chunks) == "S3 là dịch vụ lưu trữ."


def test_ignores_nested_answer_key() -> None:
    extractor = AnswerStreamExtractor()
    payload = json.dumps(
        {
            "reasoning_steps": [
                {"buoc": 1, "noi_dung": 'Khóa "answer" lồng nhau không được tính', "answer": "sai"}
            ],
            "answer": "đúng",
        },
        ensure_ascii=False,
    )
    assert _feed_all(extractor, list(payload)) == "đúng"


def test_ignores_keys_that_only_start_with_answer() -> None:
    extractor = AnswerStreamExtractor()
    payload = json.dumps({"answer_type": "text", "answer": "nội dung"})
    assert _feed_all(extractor, list(payload)) == "nội dung"


def test_decodes_escapes_and_unicode_sequences() -> None:
    extractor = AnswerStreamExtractor()
    payload = '{"answer": "Dòng 1\\nDòng 2 \\"trích dẫn\\" \\u1ed1"}'
    expected = 'Dòng 1\nDòng 2 "trích dẫn" ố'
    assert _feed_all(extractor, list(payload)) == expected
    assert extractor.answer == expected


def test_stops_after_answer_string_closes() -> None:
    extractor = AnswerStreamExtractor()
    payload = '{"answer": "A", "citations": [{"source": "tài liệu – mục", "quote": "A"}]}'
    assert _feed_all(extractor, list(payload)) == "A"
    assert extractor.finished
    assert extractor.answer == "A"


def test_non_string_answer_is_skipped_without_error() -> None:
    extractor = AnswerStreamExtractor()
    assert _feed_all(extractor, list('{"answer": null, "confidence": 0}')) == ""
    assert not extractor.answered


def test_answer_inside_markdown_fence_is_extracted() -> None:
    extractor = AnswerStreamExtractor()
    payload = '```json\n{"answer": "có hàng rào"}\n```'
    assert _feed_all(extractor, list(payload)) == "có hàng rào"
