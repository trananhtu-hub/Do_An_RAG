from __future__ import annotations

import time
from uuid import uuid4

import pytest
from app.services.conversation import ConversationConfig
from app.services.sessions.types import SessionNotFound
from session_support import (
    CONFIG_RAW,
    USER_A,
    USER_B,
    FakeChain,
    FakeGeneration,
    build_service,
    rewrite_json,
)


@pytest.fixture
def service():
    instance = build_service()
    yield instance
    instance.close()


def _completion_config(**summary: object) -> ConversationConfig:
    raw = {
        **CONFIG_RAW,
        "summary": {"enabled": True, "trigger_turns": 2, "keep_recent_turns": 1, **summary},
    }
    return ConversationConfig.from_dict(raw)


def test_dependent_question_is_rewritten_and_both_versions_are_saved() -> None:
    chain = FakeChain([rewrite_json("S3 Standard khác S3 Intelligent-Tiering thế nào về chi phí?")])
    generation = FakeGeneration(chain=chain)
    service = build_service(generation=generation)
    try:
        session = service.create_session(USER_A, title="So sánh S3")
        service.answer(USER_A, session.id, "S3 Standard khác gì S3 Intelligent-Tiering?")
        outcome = service.answer(USER_A, session.id, "Vậy còn chi phí thì sao?")

        messages = service.list_messages(USER_A, session.id)
        second_user = messages[2]
        second_assistant = messages[3]
        assert second_user.content == "Vậy còn chi phí thì sao?"
        assert (
            second_user.rewritten_query
            == "S3 Standard khác S3 Intelligent-Tiering thế nào về chi phí?"
        )
        assert second_assistant.metadata["rewritten_query"] == second_user.rewritten_query
        assert second_assistant.metadata["stream_status"] == "complete"
        assert generation.answer_calls[1][0] == second_user.rewritten_query
        assert outcome.turn.condensation.source == "llm"
        assert outcome.turn.condensation.depends_on_context is True
    finally:
        service.close()


def test_standalone_question_is_not_sent_to_rewriter() -> None:
    chain = FakeChain([rewrite_json("không dùng tới")])
    generation = FakeGeneration(chain=chain)
    service = build_service(generation=generation)
    try:
        session = service.create_session(USER_A)
        service.answer(USER_A, session.id, "S3 Standard khác gì S3 Intelligent-Tiering?")
        outcome = service.answer(
            USER_A,
            session.id,
            "Hãy giải thích chi tiết kiến trúc multi-AZ cho cơ sở dữ liệu quan hệ.",
        )
        assert outcome.turn.condensation.source == "none"
        assert outcome.turn.rewritten == (
            "Hãy giải thích chi tiết kiến trúc multi-AZ cho cơ sở dữ liệu quan hệ."
        )
        assert chain.calls == []
    finally:
        service.close()


def test_request_id_replays_instead_of_regenerating() -> None:
    generation = FakeGeneration()
    service = build_service(generation=generation)
    try:
        session = service.create_session(USER_A)
        request_id = uuid4()
        first = service.answer(
            USER_A,
            session.id,
            "S3 Standard phù hợp với loại dữ liệu nào?",
            request_id=request_id,
        )
        second = service.answer(
            USER_A,
            session.id,
            "S3 Standard phù hợp với loại dữ liệu nào?",
            request_id=request_id,
        )
        assert first.replayed is False
        assert second.replayed is True
        assert len(generation.answer_calls) == 1
        assert len(service.list_messages(USER_A, session.id)) == 2
        assert second.message is not None
        assert second.message.content == first.message.content
    finally:
        service.close()


def test_answer_rejects_unknown_or_foreign_session() -> None:
    service = build_service()
    try:
        session = service.create_session(USER_A)
        with pytest.raises(SessionNotFound, match="không thuộc"):
            service.answer(USER_B, session.id, "S3 Standard là gì?")
        with pytest.raises(SessionNotFound):
            service.answer(USER_A, uuid4(), "S3 Standard là gì?")
    finally:
        service.close()


def test_empty_question_is_rejected() -> None:
    service = build_service()
    try:
        session = service.create_session(USER_A)
        with pytest.raises(ValueError):
            service.prepare(USER_A, session.id, "   ")
    finally:
        service.close()


def test_delete_session_and_delete_all() -> None:
    service = build_service()
    try:
        first = service.create_session(USER_A)
        second = service.create_session(USER_A)
        other = service.create_session(USER_B)

        assert service.delete_session(USER_B, first.id) is False
        assert service.delete_session(USER_A, first.id) is True
        assert service.count_sessions(USER_A) == 1
        assert service.delete_all_sessions(USER_A) == 1
        assert service.count_sessions(USER_A) == 0
        assert service.count_sessions(USER_B) == 1
        assert service.repository.get_session(USER_B, other.id) is not None
        assert second.id is not None
    finally:
        service.close()


def test_conversation_context_stays_within_token_budget_after_twelve_turns() -> None:
    generation = FakeGeneration(
        answer="S3 Standard phù hợp với dữ liệu truy cập thường xuyên.",
    )
    service = build_service(generation=generation)
    try:
        session = service.create_session(USER_A)
        long_question = (
            "Trong kiến trúc nhiều tài khoản AWS, hãy giải thích cách tổ chức "
            "Amazon S3 và IAM sao cho tách biệt dữ liệu giữa các phòng ban."
        )
        for _ in range(12):
            service.answer(USER_A, session.id, long_question)

        turn = service.prepare(USER_A, session.id, "Giải thích thêm về S3 bucket policy.")
        assert turn.conversation.tokens <= CONFIG_RAW["context"]["max_conversation_tokens"]
        assert turn.conversation.trimmed is True
        assert turn.conversation.message_count < 24
        conversation_arg = generation.answer_calls[-1][1].get("conversation")
        assert conversation_arg is None or len(conversation_arg) <= 900
    finally:
        service.close()


def test_topic_shift_drops_prior_turns_from_conversation_context() -> None:
    chain = FakeChain([rewrite_json("không dùng tới")])
    generation = FakeGeneration(chain=chain)
    service = build_service(generation=generation)
    try:
        session = service.create_session(USER_A)
        service.answer(USER_A, session.id, "S3 Standard phù hợp với loại dữ liệu nào?")
        service.answer(USER_A, session.id, "Đổi chủ đề: trong IAM, MFA nên bật cho những ai?")
        turn = service.prepare(USER_A, session.id, "Có bắt buộc MFA cho mọi user không?")

        assert "MFA" in turn.conversation.text
        assert "S3 Standard phù hợp với loại dữ liệu nào?" not in turn.conversation.text
    finally:
        service.close()


def test_summary_is_generated_and_reused_in_next_turn() -> None:
    chain = FakeChain(
        ["Người học đang tìm hiểu S3 Standard, Intelligent-Tiering và bucket policy."]
    )
    generation = FakeGeneration(chain=chain)
    service = build_service(generation=generation, config=_completion_config())
    try:
        session = service.create_session(USER_A)
        service.answer(USER_A, session.id, "S3 Standard phù hợp với loại dữ liệu nào?")
        service.answer(USER_A, session.id, "S3 Intelligent-Tiering khác gì S3 Standard?")
        service.answer(USER_A, session.id, "Khi nào nên dùng S3 Glacier Deep Archive?")
        service.wait_for_background(timeout=10.0)

        stored = service.get_session(USER_A, session.id)
        assert stored.summary and "S3 Standard" in stored.summary
        assert stored.summary_message_count > 0

        turn = service.prepare(USER_A, session.id, "Hãy tóm tắt lại các điểm chính đã bàn.")
        assert turn.conversation.summary_used is True
        assert "TÓM TẮT HỘI THOẠI" in turn.conversation.text
        assert turn.conversation.message_count <= 2
    finally:
        service.close()


_TEN_TURN_QUESTIONS = [
    "Phân tích các ưu điểm chính của dịch vụ Amazon S3 Standard trong hệ thống.",
    "Trình bày cách dịch vụ S3 Intelligent-Tiering tự động chuyển lớp lưu trữ dữ liệu.",
    "Mô tả đặc điểm và ứng dụng của S3 Glacier Deep Archive trong lưu trữ dài hạn.",
    "Phân biệt vai trò của IAM role và IAM user trong môi trường nhiều tài khoản.",
    "Phân biệt cách hoạt động của security group và network ACL trong VPC.",
    "Mô tả kiến trúc Multi-AZ của Amazon RDS và lợi ích khi triển khai.",
    "Liệt kê các routing policy phổ biến của Route 53 kèm ví dụ sử dụng.",
    "Phân tích mô hình thực thi và giới hạn của AWS Lambda trong ứng dụng.",
    "Trình bày nguyên tắc thiết kế partition key cho bảng DynamoDB hiệu năng cao.",
    "Phân tích lợi ích của Amazon CloudFront đối với độ trễ và băng thông.",
    "So sánh ưu nhược điểm của bucket policy và ACL trong Amazon S3.",
    "Trình bày đặc điểm của các loại EBS volume phổ biến trên AWS.",
    "Phân tích cách Elastic Load Balancing phân phối lưu lượng cho ứng dụng HTTP.",
]

_SUMMARY_TEXT = "Người học đang ôn S3, IAM và kiến trúc multi-AZ."


def _ten_turn_config(**summary: object) -> ConversationConfig:
    raw = {
        **CONFIG_RAW,
        "summary": {
            "enabled": True,
            "trigger_turns": 10,
            "keep_recent_turns": 6,
            **summary,
        },
        "context": {
            "max_conversation_tokens": 1500,
            "chars_per_token": 3.0,
            "max_message_chars": 600,
        },
    }
    return ConversationConfig.from_dict(raw)


def test_summary_is_used_on_the_turn_after_ten_turns() -> None:
    chain = FakeChain([_SUMMARY_TEXT])
    generation = FakeGeneration(chain=chain)
    service = build_service(generation=generation, config=_ten_turn_config())
    try:
        session = service.create_session(USER_A)
        turns = [service.answer(USER_A, session.id, question) for question in _TEN_TURN_QUESTIONS]

        used = [turn.turn.conversation.summary_used for turn in turns]
        assert used == [False] * 10 + [True] * 3
        assert turns[10].turn.summary_source == "stored"
        assert turns[10].message is not None
        assert turns[10].message.metadata["summary_source"] == "stored"
        assert "TÓM TẮT HỘI THOẠI TRƯỚC ĐÓ" in turns[10].turn.conversation.text
        assert turns[10].turn.conversation.message_count == 12
        assert turns[10].turn.conversation.tokens <= 1500

        stored = service.get_session(USER_A, session.id)
        assert stored.summary == _SUMMARY_TEXT
        assert stored.summary_message_count == 8
    finally:
        service.close()


class _SlowChain(FakeChain):
    def __init__(self, texts: list[str], delay: float = 0.4) -> None:
        super().__init__(texts)
        self.delay = delay

    def complete(self, messages, **kwargs):
        time.sleep(self.delay)
        return super().complete(messages, **kwargs)


def test_slow_background_summary_falls_back_inline_on_next_turn() -> None:
    chain = _SlowChain([_SUMMARY_TEXT])
    generation = FakeGeneration(chain=chain)
    service = build_service(
        generation=generation,
        config=_ten_turn_config(await_ms=30),
    )
    try:
        session = service.create_session(USER_A)
        for question in _TEN_TURN_QUESTIONS[:10]:
            service.answer(USER_A, session.id, question)

        outcome = service.answer(USER_A, session.id, _TEN_TURN_QUESTIONS[10])

        assert outcome.turn.conversation.summary_used is True
        assert outcome.turn.summary_source == "inline_fallback"
        assert "Tóm tắt tạm" in outcome.turn.conversation.text
        assert outcome.message is not None
        assert outcome.message.metadata["summary_source"] == "inline_fallback"

        service.wait_for_background(timeout=10.0)
        stored = service.get_session(USER_A, session.id)
        assert stored.summary == _SUMMARY_TEXT
    finally:
        service.close()
