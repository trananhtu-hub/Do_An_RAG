from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

ROLES = ("user", "assistant", "system")


class SessionNotFound(LookupError):
    """Phiên không tồn tại hoặc không thuộc người dùng hiện tại."""


class SessionStoreError(RuntimeError):
    """Không truy cập được kho phiên (lỗi kết nối, lỗi truy vấn)."""


@dataclass(frozen=True)
class SessionRecord:
    id: UUID
    user_id: UUID
    title: str | None
    summary: str | None
    summary_message_count: int
    message_count: int
    token_count: int
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "title": self.title,
            "summary": self.summary,
            "summary_message_count": self.summary_message_count,
            "message_count": self.message_count,
            "token_count": self.token_count,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True)
class MessageRecord:
    id: UUID
    session_id: UUID
    role: str
    content: str
    rewritten_query: str | None
    citations: list[dict[str, Any]]
    token_count: int
    request_id: UUID | None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    seq: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "role": self.role,
            "content": self.content,
            "rewritten_query": self.rewritten_query,
            "citations": self.citations,
            "token_count": self.token_count,
            "request_id": str(self.request_id) if self.request_id else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "seq": self.seq,
        }


class SessionRepository(Protocol):
    def create_session(
        self,
        user_id: UUID,
        *,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionRecord: ...

    def list_sessions(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[SessionRecord]: ...

    def count_sessions(self, user_id: UUID) -> int: ...

    def get_session(self, user_id: UUID, session_id: UUID) -> SessionRecord | None: ...

    def update_session(
        self, user_id: UUID, session_id: UUID, *, title: str | None
    ) -> SessionRecord | None: ...

    def delete_session(self, user_id: UUID, session_id: UUID) -> bool: ...

    def delete_all_sessions(self, user_id: UUID) -> int: ...

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
    ) -> MessageRecord | None: ...

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
    ) -> tuple[MessageRecord, MessageRecord] | None: ...

    def update_message(
        self,
        user_id: UUID,
        message_id: UUID,
        *,
        content: str | None = None,
        citations: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        token_count: int | None = None,
    ) -> MessageRecord | None: ...

    def get_message_by_request(
        self, user_id: UUID, session_id: UUID, request_id: UUID
    ) -> MessageRecord | None: ...

    def list_messages(
        self, user_id: UUID, session_id: UUID, *, limit: int = 200, offset: int = 0
    ) -> list[MessageRecord]: ...

    def recent_messages(
        self, user_id: UUID, session_id: UUID, limit: int
    ) -> list[MessageRecord]: ...

    def set_summary(
        self,
        user_id: UUID,
        session_id: UUID,
        *,
        summary: str,
        summary_message_count: int,
    ) -> SessionRecord | None: ...
