from __future__ import annotations

import json
import time
from typing import Any
from uuid import UUID

from app.services.chat import ChatService
from app.services.conversation import (
    ConversationConfig,
    ConversationPromptLibrary,
    ConversationSummarizer,
    QueryCondenser,
)
from app.services.generation import AnswerDelta
from app.services.generation.providers import LLMError, LLMResponse, Usage
from app.services.generation.types import (
    AnswerPayload,
    Citation,
    CitationReport,
    GenerationResult,
)
from app.services.sessions.memory import InMemorySessionRepository

USER_A = UUID("11111111-1111-4111-8111-111111111111")
USER_B = UUID("22222222-2222-4222-8222-222222222222")

CONFIG_RAW: dict[str, Any] = {
    "version": 1,
    "prompt_version": "v1",
    "condensation": {"enabled": True},
    "summary": {"enabled": False},
    "context": {
        "max_conversation_tokens": 300,
        "chars_per_token": 3.0,
        "max_message_chars": 600,
    },
}


def make_result(answer: str, *, streaming: bool = False, ttft_ms: float = 15.0) -> GenerationResult:
    citation = Citation(source="S3 Storage Classes – S3 Standard", quote="S3 Standard")
    payload = AnswerPayload(
        answer=answer,
        citations=[citation],
        confidence=0.9,
    )
    return GenerationResult(
        question="q",
        payload=payload,
        provider="fake",
        model="fake-model",
        prompt_version="v1",
        prompt_mode="strict",
        thinking_level="low",
        latency_ms=42.0,
        usage_input_tokens=100,
        usage_output_tokens=40,
        cost_usd=0.0,
        fallback_used=None,
        attempts=("fake",),
        schema_retries=0,
        citation_report=CitationReport(
            inline_citations=(citation.source,),
            matched=(citation.source,),
        ),
        ttft_ms=ttft_ms,
        streaming=streaming,
    )


class FakeChain:
    """Thay FallbackChain cho bộ viết lại câu hỏi và bộ tóm tắt."""

    def __init__(self, texts: list[str] | None = None) -> None:
        self.texts = list(texts or [])
        self.calls: list[list[Any]] = []

    def complete(self, messages, **kwargs) -> LLMResponse:
        self.calls.append(list(messages))
        text = self.texts.pop(0) if len(self.texts) > 1 else (self.texts[0] if self.texts else "")
        return LLMResponse(
            text=text,
            model="fake-model",
            provider="fake",
            usage=Usage.from_counts(30, 10),
            latency_ms=5.0,
        )


class FakeGeneration:
    """Thay GenerationService: trả kết quả dựng sẵn và stream theo kịch bản."""

    def __init__(
        self,
        *,
        chain: FakeChain | None = None,
        answer: str = "S3 Standard phù hợp với dữ liệu truy cập thường xuyên.",
        chunks: tuple[str, ...] = (
            "S3 Standard ",
            "phù hợp với ",
            "dữ liệu truy cập thường xuyên.",
        ),
        fail_at_chunk: int | None = None,
        chunk_delay: float = 0.0,
    ) -> None:
        self.chain = chain or FakeChain()
        self.answer_text = answer
        self.chunks = chunks
        self.fail_at_chunk = fail_at_chunk
        self.chunk_delay = chunk_delay
        self.answer_calls: list[tuple[str, dict[str, Any]]] = []
        self.stream_calls: list[tuple[str, dict[str, Any]]] = []
        self.stream_closed = 0

    def answer(self, question: str, **kwargs) -> GenerationResult:
        self.answer_calls.append((question, kwargs))
        return make_result(self.answer_text)

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
                yield AnswerDelta(result=make_result(self.answer_text, streaming=True))
            finally:
                self.stream_closed += 1

        return produce()


def build_service(
    *,
    generation: FakeGeneration | None = None,
    config: ConversationConfig | None = None,
    repository: InMemorySessionRepository | None = None,
) -> ChatService:
    cfg = config or ConversationConfig.from_dict(CONFIG_RAW)
    gen = generation or FakeGeneration()
    repo = repository or InMemorySessionRepository()
    prompts = ConversationPromptLibrary(cfg.prompt_root)
    condenser = QueryCondenser(cfg.condensation, gen.chain, prompts)  # type: ignore[arg-type]
    summarizer = ConversationSummarizer(cfg, gen.chain, prompts, repo)  # type: ignore[arg-type]
    return ChatService(
        repo,
        gen,  # type: ignore[arg-type]
        cfg,
        condenser=condenser,
        summarizer=summarizer,
    )


def rewrite_json(rewritten: str, *, depends: bool = True) -> str:
    return json.dumps({"rewritten": rewritten, "depends_on_context": depends}, ensure_ascii=False)


__all__ = [
    "CONFIG_RAW",
    "FakeChain",
    "FakeGeneration",
    "USER_A",
    "USER_B",
    "build_service",
    "make_result",
    "rewrite_json",
]
