from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

AbstentionType = Literal["none", "no_evidence", "out_of_scope", "unknown"]


class ReasoningStep(BaseModel):
    buoc: int = Field(default=0, ge=0)
    noi_dung: str = Field(min_length=1)
    can_cu: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    source: str = Field(min_length=1)
    quote: str = ""


class AnswerPayload(BaseModel):
    """Schema đầu ra bắt buộc của tầng sinh câu trả lời."""

    answer: str = Field(min_length=1)
    reasoning_steps: list[ReasoningStep] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    abstained: bool = False
    abstention_type: AbstentionType = "none"
    nearest_topics: list[str] = Field(default_factory=list)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, value: Any) -> float:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        if number > 1.0 and number <= 100.0:
            number = number / 100.0
        return min(1.0, max(0.0, number))

    @field_validator("abstained", mode="before")
    @classmethod
    def _coerce_abstained(cls, value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "có")
        return bool(value)

    @field_validator("reasoning_steps", mode="before")
    @classmethod
    def _coerce_steps(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, list):
            return [{"noi_dung": item} if isinstance(item, str) else item for item in value]
        return value

    @field_validator("citations", mode="before")
    @classmethod
    def _coerce_citations(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, list):
            return [{"source": item} if isinstance(item, str) else item for item in value]
        return value

    @field_validator("nearest_topics", mode="before")
    @classmethod
    def _coerce_topics(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value


@dataclass(frozen=True)
class CitationIssue:
    citation: str
    reason: str


@dataclass(frozen=True)
class CitationReport:
    """Kết quả đối chiếu trích dẫn với ngữ cảnh đã cấp cho mô hình."""

    inline_citations: tuple[str, ...] = ()
    matched: tuple[str, ...] = ()
    unmatched: tuple[CitationIssue, ...] = ()
    quotes_checked: int = 0
    quotes_found: int = 0

    @property
    def citation_validity(self) -> float:
        total = len(self.inline_citations)
        return 1.0 if total == 0 else round(len(self.matched) / total, 4)

    @property
    def quote_grounding(self) -> float:
        if self.quotes_checked == 0:
            return 1.0
        return round(self.quotes_found / self.quotes_checked, 4)

    @property
    def ok(self) -> bool:
        return not self.unmatched and self.quote_grounding >= 0.99


@dataclass(frozen=True)
class GenerationResult:
    question: str
    payload: AnswerPayload
    provider: str
    model: str
    prompt_version: str
    prompt_mode: str
    thinking_level: str
    latency_ms: float
    usage_input_tokens: int
    usage_output_tokens: int
    cost_usd: float
    fallback_used: str | None
    attempts: tuple[str, ...]
    schema_retries: int
    citation_report: CitationReport
    warnings: tuple[str, ...] = ()
    retrieval_query_type: str | None = None
    chunk_ids: tuple[str, ...] = ()
    context_tokens_estimate: int = 0
    raw_text: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    ttft_ms: float = 0.0
    streaming: bool = False
    status: str = "complete"
    conversation_tokens: int = 0
