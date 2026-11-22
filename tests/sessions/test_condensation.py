from __future__ import annotations

import pytest
from app.services.conversation import (
    ConversationConfig,
    ConversationPromptLibrary,
    QueryCondenser,
)
from session_support import CONFIG_RAW, FakeChain, rewrite_json

HISTORY = [
    ("user", "Amazon S3 Standard lưu dữ liệu thường xuyên truy cập như thế nào?"),
    ("assistant", "S3 Standard dành cho dữ liệu được truy cập thường xuyên."),
]


def _build_condenser(texts: list[str]) -> tuple[QueryCondenser, FakeChain]:
    config = ConversationConfig.from_dict(CONFIG_RAW)
    chain = FakeChain(texts)
    prompts = ConversationPromptLibrary(config.prompt_root)
    return QueryCondenser(config.condensation, chain, prompts), chain  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "question",
    [
        "So với EBS thì khác ở đâu?",
        "Cái nào giúp tăng khả năng đọc?",
        "Khi instance chính lỗi thì cái nào tự chuyển?",
        "Có khôi phục được về một giờ trước không?",
        "Nếu ảnh gốc không thể tạo lại thì sao?",
        "Nếu chỉ lưu 20 ngày thì sao?",
        "Còn batch xử lý ảnh chạy 2 giờ mỗi đêm thì sao?",
    ],
)
def test_follow_up_questions_trigger_a_rewrite(question: str) -> None:
    condenser, chain = _build_condenser([rewrite_json("Câu hỏi độc lập đã viết lại?")])
    result = condenser.condense(question, HISTORY)
    assert chain.calls, f"Câu hỏi phụ thuộc ngữ cảnh không được viết lại: {question}"
    assert result.source == "llm"
    assert result.rewritten == "Câu hỏi độc lập đã viết lại?"


def test_topic_shift_prefix_is_stripped_without_calling_the_model() -> None:
    condenser, chain = _build_condenser([rewrite_json("không dùng tới")])
    result = condenser.condense("Đổi chủ đề: trong IAM, MFA nên bật cho những ai?", HISTORY)
    assert result.source == "topic_shift"
    assert result.rewritten == "trong IAM, MFA nên bật cho những ai?"
    assert result.depends_on_context is False
    assert chain.calls == []
