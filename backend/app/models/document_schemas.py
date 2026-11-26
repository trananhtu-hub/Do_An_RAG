from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class DocumentSummary(BaseModel):
    id: UUID
    title: str
    source_key: str | None
    page_count: int | None


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary]
    total: int
