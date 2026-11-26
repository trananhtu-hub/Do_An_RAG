from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class QuizDomain(BaseModel):
    code: str
    label: str
    count: int


class QuizDomainsResponse(BaseModel):
    items: list[QuizDomain]
    total: int


class QuizQuestionOption(BaseModel):
    label: str
    text: str


class QuizQuestion(BaseModel):
    id: UUID
    question: str
    domain: str | None
    options: list[QuizQuestionOption]


class QuizQuestionsRequest(BaseModel):
    domain: str | None = None
    count: int = Field(default=5, ge=1, le=20)


class QuizQuestionsResponse(BaseModel):
    items: list[QuizQuestion]


class QuizAnswer(BaseModel):
    question_id: UUID
    selected: str | None = Field(default=None, max_length=2000)


class QuizSubmitRequest(BaseModel):
    answers: list[QuizAnswer] = Field(min_length=1, max_length=20)
    domain: str | None = None
    duration_seconds: int | None = Field(default=None, ge=0, le=86_400)

    @field_validator("answers")
    @classmethod
    def _unique_questions(cls, value: list[QuizAnswer]) -> list[QuizAnswer]:
        seen: set[UUID] = set()
        for answer in value:
            if answer.question_id in seen:
                raise ValueError("Mỗi câu hỏi chỉ được trả lời một lần")
            seen.add(answer.question_id)
        return value


class QuizResultItem(BaseModel):
    question_id: UUID
    question: str
    domain: str | None
    selected: str | None
    correct_answer: str
    is_correct: bool
    explanation: str | None
    source: str | None


class QuizSubmitResponse(BaseModel):
    attempt_id: UUID
    domain: str | None
    total: int
    correct: int
    score: float
    items: list[QuizResultItem]


class QuizAttemptSummary(BaseModel):
    id: UUID
    domain: str | None
    total: int
    correct: int
    score: float
    created_at: datetime


class QuizAttemptsResponse(BaseModel):
    items: list[QuizAttemptSummary]
    total: int


class DeleteQuizAttemptsResponse(BaseModel):
    deleted: int
