from __future__ import annotations

import time
from typing import Any
from uuid import UUID, uuid4

from app.services.chat import ChatService
from app.services.conversation import (
    CondensationResult,
    ConversationConfig,
    estimate_tokens,
)
from app.services.generation import AnswerDelta
from app.services.generation.providers import LLMError
from app.services.generation.types import (
    AnswerPayload,
    Citation,
    CitationReport,
    GenerationResult,
)
from app.services.sessions.memory import InMemorySessionRepository

USER_A = UUID("11111111-1111-4111-8111-111111111111")
ANSWER = "S3 Standard phù hợp với dữ liệu truy cập thường xuyên."
CHUNKS = ("S3 Standard ", "phù hợp với ", "dữ liệu truy cập thường xuyên.")

CONFIG = ConversationConfig.from_dict(
    {
        "version": 1,
        "prompt_version": "v1",
        "condensation": {"enabled": False},
        "summary": {"enabled": False},
        "context": {"max_conversation_tokens": 400, "chars_per_token": 3.0},
    }
)


def make_result(answer: str = ANSWER, *, streaming: bool = True) -> GenerationResult:
    citation = Citation(source="S3 Storage Classes – S3 Standard", quote="S3 Standard")
    return GenerationResult(
        question="q",
        payload=AnswerPayload(answer=answer, citations=[citation], confidence=0.88),
        provider="fake",
        model="fake-model",
        prompt_version="v1",
        prompt_mode="strict",
        thinking_level="low",
        latency_ms=30.0,
        usage_input_tokens=90,
        usage_output_tokens=30,
        cost_usd=0.0,
        fallback_used=None,
        attempts=("fake",),
        schema_retries=0,
        citation_report=CitationReport(
            inline_citations=(citation.source,),
            matched=(citation.source,),
        ),
        ttft_ms=12.5,
        streaming=streaming,
    )


class StubCondenser:
    def condense(self, question: str, history, *, summary=None) -> CondensationResult:
        return CondensationResult(
            original=question,
            rewritten=question,
            source="none",
            depends_on_context=False,
            latency_ms=0.0,
            usage_tokens=0,
        )


class StubSummarizer:
    def maybe_summarize(self, user_id, session, messages):
        return None


class FakeStreamingGeneration:
    chain = None

    def __init__(
        self,
        *,
        chunks: tuple[str, ...] = CHUNKS,
        answer: str = ANSWER,
        fail_at_chunk: int | None = None,
        chunk_delay: float = 0.0,
    ) -> None:
        self.chunks = chunks
        self.answer_text = answer
        self.fail_at_chunk = fail_at_chunk
        self.chunk_delay = chunk_delay
        self.answer_calls: list[tuple[str, dict[str, Any]]] = []
        self.stream_calls: list[tuple[str, dict[str, Any]]] = []
        self.stream_closed = 0

    def answer(self, question: str, **kwargs) -> GenerationResult:
        self.answer_calls.append((question, kwargs))
        return make_result(self.answer_text, streaming=False)

    def answer_stream(self, question: str, **kwargs):
        self.stream_calls.append((question, kwargs))

        def produce():
            try:
                for index, piece in enumerate(self.chunks):
                    if self.fail_at_chunk is not None and index >= self.fail_at_chunk:
                        raise LLMError("Mô hình giả lập gặp lỗi", provider="fake")
                    if self.chunk_delay:
                        time.sleep(self.chunk_delay)
                    yield AnswerDelta(text=piece)
                if self.fail_at_chunk is not None:
                    raise LLMError("Mô hình giả lập gặp lỗi", provider="fake")
                yield AnswerDelta(result=make_result(self.answer_text))
            finally:
                self.stream_closed += 1

        return produce()


def build_service(generation: FakeStreamingGeneration | None = None) -> ChatService:
    gen = generation or FakeStreamingGeneration()
    return ChatService(
        InMemorySessionRepository(),
        gen,  # type: ignore[arg-type]
        CONFIG,
        condenser=StubCondenser(),  # type: ignore[arg-type]
        summarizer=StubSummarizer(),  # type: ignore[arg-type]
    )


def approx_tokens(text: str) -> int:
    return estimate_tokens(text, CONFIG.context.chars_per_token)


__all__ = [
    "ANSWER",
    "CHUNKS",
    "CONFIG",
    "FakeStreamingGeneration",
    "USER_A",
    "approx_tokens",
    "build_service",
    "make_result",
    "uuid4",
]
