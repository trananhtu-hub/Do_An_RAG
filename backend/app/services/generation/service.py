from __future__ import annotations

import threading
import time
from collections.abc import Sequence
from pathlib import Path

from ..retrieval.types import RetrievalResult, RetrievedChunk
from .citations import check_citations
from .config import GenerationConfig, load_generation_config
from .context import BuiltContext, build_context
from .logger import QueryLogWriter
from .prompts import PromptLibrary, mode_for_query_type
from .providers import (
    FallbackChain,
    LLMMessage,
    LLMResponse,
    build_provider_chain,
)
from .schema import SchemaError, parse_answer, repair_message
from .types import AnswerPayload, GenerationResult

SCHEMA_TEMPLATE = """{
  "answer": "...",
  "reasoning_steps": [{"buoc": 1, "noi_dung": "...", "can_cu": ["tài liệu – mục"]}],
  "citations": [{"source": "tài liệu – mục", "quote": "..."}],
  "confidence": 0.0,
  "abstained": false,
  "abstention_type": "none",
  "nearest_topics": []
}"""


class GenerationService:
    def __init__(
        self,
        config: GenerationConfig,
        chain: FallbackChain,
        *,
        retrieval: object | None = None,
        prompts: PromptLibrary | None = None,
        log_writer: QueryLogWriter | None = None,
    ) -> None:
        self.config = config
        self.chain = chain
        self.retrieval = retrieval
        self.prompts = prompts or PromptLibrary(config.prompt_root)
        self.log_writer = log_writer

    def answer(
        self,
        question: str,
        *,
        chunks: Sequence[RetrievedChunk] | None = None,
        retrieval_result: RetrievalResult | None = None,
        top_k: int | None = None,
        mode: str | None = None,
        use_cot: bool = True,
        thinking_level: str | None = None,
        session_id: str | None = None,
        write_log: bool = True,
    ) -> GenerationResult:
        started = time.perf_counter()
        if chunks is None:
            if self.retrieval is None:
                raise ValueError("Cần chunks hoặc một RetrievalService để truy xuất")
            retrieval_result = self.retrieval.retrieve(question, top_k=top_k)  # type: ignore[attr-defined]
            chunks = retrieval_result.chunks
        chunks = list(chunks)
        query_type = retrieval_result.query_type if retrieval_result else None

        context = build_context(
            chunks,
            max_context_tokens=self.config.max_context_tokens,
            chars_per_token=self.config.chars_per_token,
        )
        prompt_mode = mode or mode_for_query_type(query_type)
        level = thinking_level or self.config.default_thinking_level

        if context.is_empty:
            payload = self._empty_context_payload()
            result = self._result(
                question=question,
                payload=payload,
                response=None,
                prompt_mode="abstain",
                thinking_level=level,
                latency_ms=(time.perf_counter() - started) * 1000,
                context=context,
                chunks=chunks,
                query_type=query_type,
                schema_retries=0,
                warnings=("Không có đoạn ngữ cảnh nào được truy xuất.",),
                citation_report=check_citations(payload, (), ()),
            )
            self._write_log(result, session_id, retrieval_result)
            return result

        messages = self.prompts.build(
            question=question,
            context_text=context.text,
            mode=prompt_mode,
            use_cot=use_cot,
        )
        payload, response, retries = self._complete_with_schema(messages, thinking_level=level)
        if payload.abstained:
            payload = payload.model_copy(update={"citations": []})
            if payload.confidence > 0.2:
                payload = payload.model_copy(update={"confidence": 0.2})

        citation_report = check_citations(payload, context.blocks, chunks)
        warnings = self._warnings(payload, citation_report, context)
        result = self._result(
            question=question,
            payload=payload,
            response=response,
            prompt_mode=prompt_mode,
            thinking_level=level,
            latency_ms=(time.perf_counter() - started) * 1000,
            context=context,
            chunks=chunks,
            query_type=query_type,
            schema_retries=retries,
            warnings=warnings,
            citation_report=citation_report,
        )
        self._write_log(result, session_id, retrieval_result)
        return result

    def _complete_with_schema(
        self,
        messages: list[LLMMessage],
        *,
        thinking_level: str,
    ) -> tuple[AnswerPayload, LLMResponse, int]:
        attempt_messages = list(messages)
        total_input = 0
        total_output = 0
        total_cost = 0.0
        total_latency = 0.0
        last_response: LLMResponse | None = None
        last_error: SchemaError | None = None
        for attempt in range(self.config.schema_retries + 1):
            response = self.chain.complete(
                attempt_messages,
                thinking_level=thinking_level,
                max_output_tokens=self.config.max_output_tokens,
                json_mode=True,
            )
            last_response = response
            total_input += response.usage.input_tokens
            total_output += response.usage.output_tokens
            total_cost += response.cost_usd
            total_latency += response.latency_ms
            try:
                payload = parse_answer(response.text)
            except SchemaError as exc:
                last_error = exc
                if attempt >= self.config.schema_retries:
                    break
                attempt_messages = [
                    *attempt_messages,
                    LLMMessage(role="assistant", content=response.text[:4000]),
                    LLMMessage(
                        role="user",
                        content=repair_message(exc, SCHEMA_TEMPLATE),
                    ),
                ]
                continue
            assert last_response is not None
            combined = LLMResponse(
                text=last_response.text,
                model=last_response.model,
                provider=last_response.provider,
                usage=last_response.usage.__class__.from_counts(total_input, total_output),
                latency_ms=round(total_latency, 2),
                cost_usd=round(total_cost, 8),
                finish_reason=last_response.finish_reason,
                fallback_used=last_response.fallback_used,
                attempts=last_response.attempts,
                raw=last_response.raw,
            )
            return payload, combined, attempt
        assert last_error is not None
        raise last_error

    def _result(
        self,
        *,
        question: str,
        payload: AnswerPayload,
        response: LLMResponse | None,
        prompt_mode: str,
        thinking_level: str,
        latency_ms: float,
        context: BuiltContext,
        chunks: Sequence[RetrievedChunk],
        query_type: str | None,
        schema_retries: int,
        warnings: tuple[str, ...],
        citation_report,
    ) -> GenerationResult:
        return GenerationResult(
            question=question,
            payload=payload,
            provider=response.provider if response else "none",
            model=response.model if response else "none",
            prompt_version=self.config.prompt_version,
            prompt_mode=prompt_mode,
            thinking_level=thinking_level,
            latency_ms=round(latency_ms, 2),
            usage_input_tokens=response.usage.input_tokens if response else 0,
            usage_output_tokens=response.usage.output_tokens if response else 0,
            cost_usd=response.cost_usd if response else 0.0,
            fallback_used=response.fallback_used if response else None,
            attempts=response.attempts if response else (),
            schema_retries=schema_retries,
            citation_report=citation_report,
            warnings=warnings,
            retrieval_query_type=query_type,
            chunk_ids=tuple(chunk.child_id for chunk in chunks),
            context_tokens_estimate=context.estimated_tokens,
            raw_text=response.text if response else "",
            extra={"provider_latency_ms": response.latency_ms if response else 0.0},
        )

    def _warnings(
        self,
        payload: AnswerPayload,
        citation_report,
        context: BuiltContext,
    ) -> tuple[str, ...]:
        warnings: list[str] = []
        if not payload.abstained and payload.confidence < self.config.confidence_warning_threshold:
            warnings.append(
                f"Độ tin cậy {payload.confidence:.2f} dưới ngưỡng "
                f"{self.config.confidence_warning_threshold:.2f}; cần nêu rõ giới hạn."
            )
        if self.config.require_citation and not payload.abstained:
            has_inline = bool(citation_report.inline_citations)
            if not payload.citations and not has_inline:
                warnings.append("Câu trả lời không có trích dẫn nào.")
        if citation_report.unmatched:
            warnings.append(
                f"{len(citation_report.unmatched)} trích dẫn không khớp ngữ cảnh đã cấp."
            )
        if context.dropped_blocks:
            warnings.append(f"Đã lược {context.dropped_blocks} đoạn do vượt ngân sách ngữ cảnh.")
        return tuple(warnings)

    def _empty_context_payload(self) -> AnswerPayload:
        return AnswerPayload(
            answer=(
                "Mình chưa truy xuất được đoạn tài liệu nào cho câu hỏi này, nên không thể "
                "trả lời có căn cứ. Bạn thử diễn đạt lại câu hỏi hoặc hỏi về một chủ đề "
                "khác trong tài liệu SAA-C03."
            ),
            reasoning_steps=[],
            citations=[],
            confidence=0.0,
            abstained=True,
            abstention_type="no_evidence",
            nearest_topics=[],
        )

    def _write_log(
        self,
        result: GenerationResult,
        session_id: str | None,
        retrieval_result: RetrievalResult | None,
    ) -> None:
        if self.log_writer is None:
            return
        self.log_writer.write(
            result,
            session_id=session_id,
            rewritten_query=retrieval_result.normalized_query if retrieval_result else None,
        )

    def close(self) -> None:
        self.chain.close()


_service: GenerationService | None = None
_service_lock = threading.Lock()


def build_default_service(
    config_path: str | Path | None = None,
    *,
    retrieval: object | None = None,
) -> GenerationService:
    from .settings import load_environment

    env = load_environment()
    config = load_generation_config(config_path)
    chain = build_provider_chain(config, environ=env)
    if retrieval is None:
        from ..retrieval import get_service as get_retrieval_service

        retrieval = get_retrieval_service()
    writer = QueryLogWriter(
        env.get("DATABASE_URL"),
        enabled=config.logging.enabled,
        table=config.logging.table,
    )
    return GenerationService(
        config,
        chain,
        retrieval=retrieval,
        prompts=PromptLibrary(config.prompt_root),
        log_writer=writer,
    )


def get_service() -> GenerationService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = build_default_service()
    return _service


def reset_service() -> None:
    global _service
    with _service_lock:
        if _service is not None:
            _service.close()
        _service = None


def generate(question: str, **kwargs) -> GenerationResult:
    return get_service().answer(question, **kwargs)
