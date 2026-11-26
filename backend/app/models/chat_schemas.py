from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

MAX_QUESTION_CHARS = 4000


class SessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    metadata: dict[str, Any] | None = None


class SessionUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Tiêu đề không được để trống")
        return value


class SessionResponse(BaseModel):
    id: UUID
    title: str | None
    message_count: int
    token_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, session) -> SessionResponse:
        return cls(
            id=session.id,
            title=session.title,
            message_count=session.message_count,
            token_count=session.token_count,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )


class SessionListResponse(BaseModel):
    items: list[SessionResponse]
    total: int


class MessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    rewritten_query: str | None
    citations: list[dict[str, Any]]
    token_count: int
    request_id: UUID | None
    metadata: dict[str, Any]
    created_at: datetime
    seq: int

    @classmethod
    def from_record(cls, message) -> MessageResponse:
        return cls(
            id=message.id,
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            rewritten_query=message.rewritten_query,
            citations=message.citations,
            token_count=message.token_count,
            request_id=message.request_id,
            metadata=message.metadata,
            created_at=message.created_at,
            seq=message.seq,
        )


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    total: int


class DeleteAllSessionsResponse(BaseModel):
    deleted: int


class ChatRequest(BaseModel):
    session_id: UUID | None = None
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    request_id: UUID | None = None
    mode: Literal["fast", "step_by_step"] | None = None
    language: Literal["vi", "en"] | None = None
    model: str | None = Field(default=None, max_length=100)

    @field_validator("question")
    @classmethod
    def _strip_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Câu hỏi không được để trống")
        return value


class ChatResponse(BaseModel):
    session_id: UUID
    message_id: UUID | None
    answer: str
    citations: list[dict[str, Any]]
    rewritten_query: str
    confidence: float
    abstained: bool
    abstention_type: str
    provider: str
    model: str
    latency_ms: float
    usage: dict[str, int]
    warnings: list[str]
    replayed: bool = False
