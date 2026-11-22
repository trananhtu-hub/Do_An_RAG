from __future__ import annotations

import threading
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from .types import MessageRecord, SessionRecord


class InMemorySessionRepository:
    """Bản thay thế cho test và cho môi trường không có PostgreSQL."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[UUID, SessionRecord] = {}
        self._messages: dict[UUID, list[MessageRecord]] = {}
        self._order: list[UUID] = []
        self._clock = datetime(2026, 1, 1, tzinfo=UTC)
        self._seq = 0

    def _now(self) -> datetime:
        self._clock += timedelta(milliseconds=1)
        return self._clock

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def create_session(
        self,
        user_id: UUID,
        *,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionRecord:
        with self._lock:
            now = self._now()
            record = SessionRecord(
                id=uuid4(),
                user_id=user_id,
                title=title,
                summary=None,
                summary_message_count=0,
                message_count=0,
                token_count=0,
                metadata=dict(metadata or {}),
                created_at=now,
                updated_at=now,
            )
            self._sessions[record.id] = record
            self._messages[record.id] = []
            self._order.append(record.id)
            return record

    def list_sessions(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[SessionRecord]:
        with self._lock:
            owned = [
                self._sessions[sid] for sid in self._order if self._sessions[sid].user_id == user_id
            ]
            owned.sort(key=lambda record: (record.updated_at, record.created_at), reverse=True)
            return owned[offset : offset + limit]

    def count_sessions(self, user_id: UUID) -> int:
        with self._lock:
            return sum(1 for record in self._sessions.values() if record.user_id == user_id)

    def get_session(self, user_id: UUID, session_id: UUID) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None or record.user_id != user_id:
                return None
            return record

    def update_session(
        self, user_id: UUID, session_id: UUID, *, title: str | None
    ) -> SessionRecord | None:
        with self._lock:
            record = self.get_session(user_id, session_id)
            if record is None:
                return None
            updated = replace(
                record,
                title=title if title is not None else record.title,
                updated_at=self._now(),
            )
            self._sessions[session_id] = updated
            return updated

    def delete_session(self, user_id: UUID, session_id: UUID) -> bool:
        with self._lock:
            record = self.get_session(user_id, session_id)
            if record is None:
                return False
            del self._sessions[session_id]
            self._messages.pop(session_id, None)
            self._order.remove(session_id)
            return True

    def delete_all_sessions(self, user_id: UUID) -> int:
        with self._lock:
            ids = [
                session_id
                for session_id, record in self._sessions.items()
                if record.user_id == user_id
            ]
            for session_id in ids:
                del self._sessions[session_id]
                self._messages.pop(session_id, None)
                if session_id in self._order:
                    self._order.remove(session_id)
            return len(ids)

    def set_summary(
        self,
        user_id: UUID,
        session_id: UUID,
        *,
        summary: str,
        summary_message_count: int,
    ) -> SessionRecord | None:
        with self._lock:
            record = self.get_session(user_id, session_id)
            if record is None:
                return None
            updated = replace(
                record,
                summary=summary,
                summary_message_count=summary_message_count,
                updated_at=self._now(),
            )
            self._sessions[session_id] = updated
            return updated

    def begin_turn(
        self,
        user_id: UUID,
        session_id: UUID,
        *,
        question: str,
        rewritten_query: str | None = None,
        question_tokens: int = 0,
        request_id: UUID | None = None,
        assistant_metadata: dict[str, Any] | None = None,
        set_title_if_empty: bool = True,
    ) -> tuple[MessageRecord, MessageRecord] | None:
        with self._lock:
            session = self.get_session(user_id, session_id)
            if session is None:
                return None
            now = self._now()
            user_message = MessageRecord(
                id=uuid4(),
                session_id=session_id,
                role="user",
                content=question,
                rewritten_query=rewritten_query,
                citations=[],
                token_count=max(0, question_tokens),
                request_id=None,
                metadata={},
                created_at=now,
                seq=self._next_seq(),
            )
            assistant_message = MessageRecord(
                id=uuid4(),
                session_id=session_id,
                role="assistant",
                content="",
                rewritten_query=None,
                citations=[],
                token_count=0,
                request_id=request_id,
                metadata=dict(assistant_metadata or {}),
                created_at=now,
                seq=self._next_seq(),
            )
            self._messages.setdefault(session_id, []).extend([user_message, assistant_message])
            title = session.title
            if set_title_if_empty and not title:
                title = question.strip()[:80] or None
            self._sessions[session_id] = replace(
                session,
                title=title,
                message_count=session.message_count + 2,
                token_count=session.token_count + max(0, question_tokens),
                updated_at=now,
            )
            return user_message, assistant_message

    def add_message(
        self,
        user_id: UUID,
        session_id: UUID,
        *,
        role: str,
        content: str,
        rewritten_query: str | None = None,
        citations: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        token_count: int = 0,
        request_id: UUID | None = None,
        set_title_if_empty: bool = False,
    ) -> MessageRecord | None:
        with self._lock:
            session = self.get_session(user_id, session_id)
            if session is None:
                return None
            now = self._now()
            message = MessageRecord(
                id=uuid4(),
                session_id=session_id,
                role=role,
                content=content,
                rewritten_query=rewritten_query,
                citations=list(citations or []),
                token_count=max(0, token_count),
                request_id=request_id,
                metadata=dict(metadata or {}),
                created_at=now,
                seq=self._next_seq(),
            )
            self._messages.setdefault(session_id, []).append(message)
            title = session.title
            if set_title_if_empty and not title:
                title = content.strip()[:80] or None
            self._sessions[session_id] = replace(
                session,
                title=title,
                message_count=session.message_count + 1,
                token_count=session.token_count + max(0, token_count),
                updated_at=now,
            )
            return message

    def update_message(
        self,
        user_id: UUID,
        message_id: UUID,
        *,
        content: str | None = None,
        citations: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        token_count: int | None = None,
    ) -> MessageRecord | None:
        with self._lock:
            for session_id, messages in self._messages.items():
                session = self._sessions.get(session_id)
                if session is None or session.user_id != user_id:
                    continue
                for index, message in enumerate(messages):
                    if message.id != message_id:
                        continue
                    updated = replace(
                        message,
                        content=content if content is not None else message.content,
                        citations=list(citations) if citations is not None else message.citations,
                        metadata=dict(metadata) if metadata is not None else message.metadata,
                        token_count=(
                            max(0, token_count) if token_count is not None else message.token_count
                        ),
                    )
                    messages[index] = updated
                    if token_count is not None:
                        delta = max(0, token_count) - message.token_count
                        if delta:
                            self._sessions[session_id] = replace(
                                session,
                                token_count=max(0, session.token_count + delta),
                                updated_at=self._now(),
                            )
                    return updated
            return None

    def get_message_by_request(
        self, user_id: UUID, session_id: UUID, request_id: UUID
    ) -> MessageRecord | None:
        with self._lock:
            if self.get_session(user_id, session_id) is None:
                return None
            for message in self._messages.get(session_id, []):
                if message.request_id == request_id:
                    return message
            return None

    def list_messages(
        self, user_id: UUID, session_id: UUID, *, limit: int = 200, offset: int = 0
    ) -> list[MessageRecord]:
        with self._lock:
            if self.get_session(user_id, session_id) is None:
                return []
            return list(self._messages.get(session_id, []))[offset : offset + limit]

    def recent_messages(self, user_id: UUID, session_id: UUID, limit: int) -> list[MessageRecord]:
        if limit <= 0:
            return []
        with self._lock:
            if self.get_session(user_id, session_id) is None:
                return []
            return list(self._messages.get(session_id, []))[-limit:]
