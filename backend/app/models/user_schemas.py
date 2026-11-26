from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class MetaOption(BaseModel):
    code: str
    label: str
    description: str | None = None


class AppMetaResponse(BaseModel):
    models: list[MetaOption]
    default_model: str
    modes: list[MetaOption]
    languages: list[MetaOption]
    max_question_chars: int


class MeResponse(BaseModel):
    id: UUID
    email: str | None
    is_admin: bool
