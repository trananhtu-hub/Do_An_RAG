from __future__ import annotations

from uuid import uuid4

from app.services.sessions.memory import InMemorySessionRepository
from session_support import USER_A, USER_B


def _repo() -> InMemorySessionRepository:
    return InMemorySessionRepository()


def test_create_list_and_isolation_between_users() -> None:
    repo = _repo()
    first = repo.create_session(USER_A, title="Phiên A")
    second = repo.create_session(USER_B, title="Phiên B")

    assert [record.id for record in repo.list_sessions(USER_A)] == [first.id]
    assert [record.id for record in repo.list_sessions(USER_B)] == [second.id]
    assert repo.count_sessions(USER_A) == 1
    assert repo.get_session(USER_B, first.id) is None
    assert repo.get_session(USER_A, second.id) is None


def test_update_and_delete_only_own_sessions() -> None:
    repo = _repo()
    session = repo.create_session(USER_A, title="Cũ")

    assert repo.update_session(USER_B, session.id, title="Chiếm") is None
    renamed = repo.update_session(USER_A, session.id, title="Mới")
    assert renamed is not None and renamed.title == "Mới"

    assert repo.delete_session(USER_B, session.id) is False
    assert repo.delete_session(USER_A, session.id) is True
    assert repo.get_session(USER_A, session.id) is None


def test_delete_all_sessions_only_touches_owner() -> None:
    repo = _repo()
    repo.create_session(USER_A)
    repo.create_session(USER_A)
    repo.create_session(USER_B)

    assert repo.delete_all_sessions(USER_A) == 2
    assert repo.count_sessions(USER_A) == 0
    assert repo.count_sessions(USER_B) == 1


def test_begin_turn_creates_ordered_pair_and_updates_counters() -> None:
    repo = _repo()
    session = repo.create_session(USER_A)
    request_id = uuid4()

    pair = repo.begin_turn(
        USER_A,
        session.id,
        question="S3 Standard là gì?",
        rewritten_query="S3 Standard là gì?",
        question_tokens=7,
        request_id=request_id,
        assistant_metadata={"stream_status": "pending"},
    )
    assert pair is not None
    user_message, assistant_message = pair
    assert user_message.role == "user"
    assert assistant_message.role == "assistant"
    assert assistant_message.request_id == request_id
    assert assistant_message.content == ""
    assert user_message.seq < assistant_message.seq

    messages = repo.list_messages(USER_A, session.id)
    assert [message.id for message in messages] == [user_message.id, assistant_message.id]
    assert [message.seq for message in messages] == sorted(message.seq for message in messages)

    updated = repo.get_session(USER_A, session.id)
    assert updated is not None
    assert updated.message_count == 2
    assert updated.token_count == 7
    assert updated.title == "S3 Standard là gì?"


def test_begin_turn_rejects_foreign_session() -> None:
    repo = _repo()
    session = repo.create_session(USER_A)
    assert repo.begin_turn(USER_B, session.id, question="hỏi") is None


def test_update_message_and_lookup_by_request() -> None:
    repo = _repo()
    session = repo.create_session(USER_A)
    request_id = uuid4()
    _, placeholder = repo.begin_turn(USER_A, session.id, question="hỏi", request_id=request_id)

    found = repo.get_message_by_request(USER_A, session.id, request_id)
    assert found is not None and found.id == placeholder.id
    assert repo.get_message_by_request(USER_B, session.id, request_id) is None

    updated = repo.update_message(
        USER_A,
        placeholder.id,
        content="Câu trả lời",
        citations=[{"source": "S3"}],
        metadata={"stream_status": "complete"},
        token_count=4,
    )
    assert updated is not None
    assert updated.content == "Câu trả lời"
    assert updated.metadata["stream_status"] == "complete"
    assert repo.get_session(USER_A, session.id).token_count == 4


def test_recent_messages_returns_tail() -> None:
    repo = _repo()
    session = repo.create_session(USER_A)
    for index in range(5):
        repo.add_message(USER_A, session.id, role="user", content=f"câu {index}")

    tail = repo.recent_messages(USER_A, session.id, 2)
    assert [message.content for message in tail] == ["câu 3", "câu 4"]
    assert repo.recent_messages(USER_B, session.id, 2) == []
