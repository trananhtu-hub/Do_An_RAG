from __future__ import annotations

import threading
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from ..retrieval.types import RetrievalResult, RetrievedChunk
from .citations import check_citations, enrich_citations, inline_citation_sources
from .config import GenerationConfig, load_generation_config
from .context import BuiltContext, build_context, fit_context_to_tokens
from .logger import QueryLogWriter
from .prompts import PromptLibrary, mode_for_query_type
from .providers import (
    FallbackChain,
    LLMError,
    LLMMessage,
    LLMResponse,
    build_provider_chain,
)
from .schema import SchemaError, parse_answer, repair_message
from .streaming import AnswerStreamExtractor
from .tokens import PromptAudit, PromptTokenCounter, audit_prompt
from .types import AnswerPayload, Citation, GenerationResult

# Câu tra cứu đơn giản dùng mức suy luận thấp hơn để giảm TTFT, câu so sánh/nhiều
# ràng buộc giữ mức mặc định vì cần suy luận nhiều bước.
_SIMPLE_QUERY_TYPES = frozenset({"tra_cuu", "tron_thuat_ngu"})

SCHEMA_TEMPLATE = """{
  "answer": "...",
  "reasoning_steps": [{"buoc": 1, "noi_dung": "...", "can_cu": ["tài liệu – mục"]}],
  "citations": [{"source": "tài liệu – mục", "quote": "..."}],
  "confidence": 0.0,
  "abstained": false,
  "abstention_type": "none",
  "nearest_topics": []
}"""


@dataclass(frozen=True)
class AnswerDelta:
    """Một mẩu trả lời khi stream; delta có `result` là mẩu cuối cùng."""

    text: str = ""
    result: GenerationResult | None = None


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
        self.token_counter = PromptTokenCounter(chars_per_token=config.chars_per_token)

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
        conversation: str | None = None,
        conversation_tokens: int = 0,
        user_id: str | None = None,
        rewritten_query: str | None = None,
        extra_instruction: str | None = None,
    ) -> GenerationResult:
        started = time.perf_counter()
        if chunks is None:
            if self.retrieval is None:
                raise ValueError("Cần chunks hoặc một RetrievalService để truy xuất")
            retrieval_result = self.retrieval.retrieve(question, top_k=top_k)  # type: ignore[attr-defined]
            chunks = retrieval_result.chunks
        chunks = list(chunks)
        query_type = retrieval_result.query_type if retrieval_result else None

        prompt_started = time.perf_counter()
        context = build_context(
            chunks,
            max_context_tokens=self.config.max_context_tokens,
            chars_per_token=self.config.chars_per_token,
        )
        prompt_mode = mode or mode_for_query_type(query_type)
        level = thinking_level or self._default_thinking_level(query_type)

        if context.is_empty:
            prompt_ms = (time.perf_counter() - prompt_started) * 1000
            latency = (time.perf_counter() - started) * 1000
            payload = self._empty_context_payload()
            result = self._result(
                question=question,
                payload=payload,
                response=None,
                prompt_mode="abstain",
                thinking_level=level,
                latency_ms=latency,
                context=context,
                chunks=chunks,
                query_type=query_type,
                schema_retries=0,
                warnings=("Không có đoạn ngữ cảnh nào được truy xuất.",),
                citation_report=check_citations(payload, (), ()),
                conversation_tokens=conversation_tokens,
                ttft_ms=latency,
                timings_ms=self._timings(
                    retrieval_result,
                    prompt_ms=prompt_ms,
                    prefill_ms=0.0,
                    generation_ms=0.0,
                    ttft_ms=latency,
                    total_ms=latency,
                    output_tokens=0,
                ),
            )
            self._write_log(
                result,
                session_id,
                retrieval_result,
                user_id=user_id,
                rewritten_query=rewritten_query,
            )
            return result

        messages, context, prompt_audit, budget_warnings = self._build_prompt(
            question=question,
            context=context,
            prompt_mode=prompt_mode,
            use_cot=use_cot,
            conversation=conversation,
            extra_instruction=extra_instruction,
        )
        prompt_ms = (time.perf_counter() - prompt_started) * 1000
        payload, response, retries = self._complete_with_schema(messages, thinking_level=level)
        if payload.abstained:
            payload = payload.model_copy(update={"citations": []})
            if payload.confidence > 0.2:
                payload = payload.model_copy(update={"confidence": 0.2})

        citation_report = check_citations(payload, context.blocks, chunks)
        warnings = list(self._warnings(payload, citation_report, context))
        warnings.extend(budget_warnings)
        latency = (time.perf_counter() - started) * 1000
        result = self._result(
            question=question,
            payload=payload,
            response=response,
            prompt_mode=prompt_mode,
            thinking_level=level,
            latency_ms=latency,
            context=context,
            chunks=chunks,
            query_type=query_type,
            schema_retries=retries,
            warnings=warnings,
            citation_report=citation_report,
            conversation_tokens=conversation_tokens,
            prompt_audit=prompt_audit,
            ttft_ms=latency,
            timings_ms=self._timings(
                retrieval_result,
                prompt_ms=prompt_ms,
                prefill_ms=0.0,
                generation_ms=response.latency_ms if response else 0.0,
                ttft_ms=latency,
                total_ms=latency,
                output_tokens=response.usage.output_tokens if response else 0,
            ),
        )
        self._write_log(
            result, session_id, retrieval_result, user_id=user_id, rewritten_query=rewritten_query
        )
        return result

    def answer_stream(
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
        conversation: str | None = None,
        conversation_tokens: int = 0,
        user_id: str | None = None,
        rewritten_query: str | None = None,
        extra_instruction: str | None = None,
    ) -> Iterator[AnswerDelta]:
        """Stream từng mẩu nội dung của trường answer.

        Phần JSON còn lại (trích dẫn, độ tin cậy) chỉ có sau khi mô hình sinh
        xong, nên sự kiện cuối cùng mang `result` đầy đủ. Nếu client ngắt giữa
        chừng, log được ghi với status tương ứng và không ném lỗi 500.
        """
        started = time.perf_counter()
        if chunks is None:
            if self.retrieval is None:
                raise ValueError("Cần chunks hoặc một RetrievalService để truy xuất")
            retrieval_result = self.retrieval.retrieve(question, top_k=top_k)  # type: ignore[attr-defined]
            chunks = retrieval_result.chunks
        chunks = list(chunks)
        query_type = retrieval_result.query_type if retrieval_result else None

        prompt_started = time.perf_counter()
        context = build_context(
            chunks,
            max_context_tokens=self.config.max_context_tokens,
            chars_per_token=self.config.chars_per_token,
        )
        prompt_mode = mode or mode_for_query_type(query_type)
        level = thinking_level or self._default_thinking_level(query_type)

        if context.is_empty:
            prompt_ms = (time.perf_counter() - prompt_started) * 1000
            payload = self._empty_context_payload()
            latency = (time.perf_counter() - started) * 1000
            result = self._result(
                question=question,
                payload=payload,
                response=None,
                prompt_mode="abstain",
                thinking_level=level,
                latency_ms=latency,
                context=context,
                chunks=chunks,
                query_type=query_type,
                schema_retries=0,
                warnings=("Không có đoạn ngữ cảnh nào được truy xuất.",),
                citation_report=check_citations(payload, (), ()),
                ttft_ms=latency,
                streaming=True,
                conversation_tokens=conversation_tokens,
                timings_ms=self._timings(
                    retrieval_result,
                    prompt_ms=prompt_ms,
                    prefill_ms=0.0,
                    generation_ms=0.0,
                    ttft_ms=latency,
                    total_ms=latency,
                    output_tokens=0,
                ),
            )
            if write_log:
                self._write_log(
                    result,
                    session_id,
                    retrieval_result,
                    user_id=user_id,
                    rewritten_query=rewritten_query,
                )
            yield AnswerDelta(result=result)
            return

        messages, context, prompt_audit, budget_warnings = self._build_prompt(
            question=question,
            context=context,
            prompt_mode=prompt_mode,
            use_cot=use_cot,
            conversation=conversation,
            extra_instruction=extra_instruction,
        )
        prompt_done_at = time.perf_counter()
        prompt_ms = (prompt_done_at - prompt_started) * 1000
        extractor = AnswerStreamExtractor()
        parts: list[str] = []
        response: LLMResponse | None = None
        first_token_at: float | None = None
        schema_retries = 0
        extra_warnings: list[str] = []
        finished = False
        failed = False
        try:
            try:
                for delta in self.chain.complete_stream(
                    messages,
                    thinking_level=level,
                    max_output_tokens=self.config.max_output_tokens,
                    json_mode=True,
                ):
                    if delta.done:
                        response = delta.response
                        continue
                    parts.append(delta.text)
                    emitted = extractor.feed(delta.text)
                    if emitted:
                        if first_token_at is None:
                            first_token_at = time.perf_counter()
                        yield AnswerDelta(text=emitted)
            except LLMError:
                failed = True
                raise

            raw_text = "".join(parts)
            if response is not None and len(response.text) > len(raw_text):
                raw_text = response.text
            try:
                payload = parse_answer(raw_text)
            except SchemaError as exc:
                if extractor.answer.strip():
                    payload = AnswerPayload(
                        answer=extractor.answer.strip(),
                        reasoning_steps=[],
                        citations=[
                            Citation(source=source)
                            for source in inline_citation_sources(extractor.answer)
                        ],
                        confidence=0.0,
                    )
                    extra_warnings.append(
                        "Đầu ra streaming không đúng schema JSON; giữ phần nội dung trả lời "
                        f"và trích dẫn nội tuyến ({type(exc).__name__})."
                    )
                else:
                    payload, response, schema_retries = self._retry_streaming_failure(
                        messages,
                        thinking_level=level,
                        streamed=response,
                    )
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    yield AnswerDelta(text=payload.answer)

            if first_token_at is None and payload.answer:
                # Provider chỉ trả kết quả cuối, không phát delta văn bản nào;
                # vẫn chuyển nội dung cho client thành một mẩu duy nhất.
                first_token_at = time.perf_counter()
                yield AnswerDelta(text=payload.answer)

            if payload.abstained:
                payload = payload.model_copy(update={"citations": []})
                if payload.confidence > 0.2:
                    payload = payload.model_copy(update={"confidence": 0.2})

            citation_report = check_citations(payload, context.blocks, chunks)
            warnings = list(self._warnings(payload, citation_report, context))
            warnings.extend(budget_warnings)
            warnings.extend(extra_warnings)
            if response is not None and response.finish_reason == "max_tokens":
                warnings.append("Mô hình chạm giới hạn token; câu trả lời có thể bị cắt.")
            finished_at = time.perf_counter()
            latency = (finished_at - started) * 1000
            ttft = (first_token_at - started) * 1000 if first_token_at else latency
            result = self._result(
                question=question,
                payload=payload,
                response=response,
                prompt_mode=prompt_mode,
                thinking_level=level,
                latency_ms=latency,
                context=context,
                chunks=chunks,
                query_type=query_type,
                schema_retries=schema_retries,
                warnings=tuple(warnings),
                citation_report=citation_report,
                ttft_ms=ttft,
                streaming=True,
                conversation_tokens=conversation_tokens,
                prompt_audit=prompt_audit,
                timings_ms=self._timings(
                    retrieval_result,
                    prompt_ms=prompt_ms,
                    prefill_ms=(
                        (first_token_at - prompt_done_at) * 1000 if first_token_at else 0.0
                    ),
                    generation_ms=(
                        (finished_at - first_token_at) * 1000 if first_token_at else 0.0
                    ),
                    ttft_ms=ttft,
                    total_ms=latency,
                    output_tokens=response.usage.output_tokens if response else 0,
                ),
            )
            if write_log:
                self._write_log(
                    result,
                    session_id,
                    retrieval_result,
                    user_id=user_id,
                    rewritten_query=rewritten_query,
                )
            finished = True
            yield AnswerDelta(result=result)
        except Exception:
            failed = True
            raise
        finally:
            if not finished and write_log:
                self._log_unfinished(
                    question=question,
                    partial=extractor.answer,
                    response=response,
                    prompt_mode=prompt_mode,
                    thinking_level=level,
                    started=started,
                    prompt_ms=prompt_ms,
                    prompt_done_at=prompt_done_at,
                    first_token_at=first_token_at,
                    context=context,
                    chunks=chunks,
                    query_type=query_type,
                    retrieval_result=retrieval_result,
                    session_id=session_id,
                    user_id=user_id,
                    rewritten_query=rewritten_query,
                    conversation_tokens=conversation_tokens,
                    prompt_audit=prompt_audit,
                    status="error" if failed else "interrupted",
                )

    def _default_thinking_level(self, query_type: str | None) -> str:
        if query_type in _SIMPLE_QUERY_TYPES:
            return self.config.simple_query_thinking_level
        return self.config.default_thinking_level

    def _build_prompt(
        self,
        *,
        question: str,
        context: BuiltContext,
        prompt_mode: str,
        use_cot: bool,
        conversation: str | None,
        extra_instruction: str | None = None,
    ) -> tuple[list[LLMMessage], BuiltContext, PromptAudit, list[str]]:
        """Dựng prompt và ép trần ``max_prompt_tokens`` bằng tokenizer DeepSeek.

        Hội thoại bị bỏ trước nếu chỉ nó đã làm vượt trần hoặc ngân sách còn lại
        cho ngữ cảnh quá hẹp; sau đó ngữ cảnh truy xuất được cắt bằng tokenizer
        thật. Mọi lần cắt đều ghi cảnh báo để báo cáo trung thực.
        """
        limit = self.config.max_prompt_tokens
        warnings: list[str] = []

        def build(ctx: BuiltContext, conv: str | None) -> list[LLMMessage]:
            if extra_instruction:
                return self.prompts.build(
                    question=question,
                    context_text=ctx.text,
                    mode=prompt_mode,
                    use_cot=use_cot,
                    conversation=conv,
                    extra_instruction=extra_instruction,
                )
            return self.prompts.build(
                question=question,
                context_text=ctx.text,
                mode=prompt_mode,
                use_cot=use_cot,
                conversation=conv,
            )

        def audit_of(msgs: list[LLMMessage]) -> PromptAudit:
            return audit_prompt(msgs, self.token_counter, limit_tokens=limit)

        messages = build(context, conversation)
        audit = audit_of(messages)
        if audit.over_limit and conversation:
            without_conversation = audit.total_tokens - audit.conversation_tokens
            if without_conversation <= limit:
                conversation = None
                messages = build(context, conversation)
                audit = audit_of(messages)
                warnings.append(f"Đã bỏ ngữ cảnh hội thoại vì prompt vượt ngân sách {limit} token.")
        if audit.over_limit:
            allowed = limit - (audit.total_tokens - audit.context_tokens)
            if conversation and allowed < 128:
                conversation = None
                messages = build(context, conversation)
                audit = audit_of(messages)
                warnings.append(
                    f"Đã bỏ ngữ cảnh hội thoại để nhường ngân sách {limit} token cho ngữ cảnh."
                )
                allowed = limit - (audit.total_tokens - audit.context_tokens)
            fitted = fit_context_to_tokens(
                context,
                count_tokens=self.token_counter.count,
                max_tokens=max(0, allowed),
            )
            if fitted.text != context.text:
                context = fitted
                messages = build(context, conversation)
                audit = audit_of(messages)
                warnings.append(
                    f"Đã thu ngữ cảnh truy xuất để giữ prompt trong ngân sách {limit} token "
                    f"(còn {audit.context_tokens} token ngữ cảnh)."
                )
        if audit.over_limit:
            warnings.append(f"Prompt vẫn vượt ngân sách: {audit.total_tokens} > {limit} token.")
        return messages, context, audit, warnings

    def _retry_streaming_failure(
        self,
        messages: list[LLMMessage],
        *,
        thinking_level: str,
        streamed: LLMResponse | None,
    ) -> tuple[AnswerPayload, LLMResponse, int]:
        payload, retry_response, retries = self._complete_with_schema(
            messages, thinking_level=thinking_level
        )
        if streamed is None:
            return payload, retry_response, retries + 1
        usage = retry_response.usage.__class__.from_counts(
            retry_response.usage.input_tokens + streamed.usage.input_tokens,
            retry_response.usage.output_tokens + streamed.usage.output_tokens,
        )
        combined = LLMResponse(
            text=retry_response.text,
            model=retry_response.model,
            provider=retry_response.provider,
            usage=usage,
            latency_ms=round(retry_response.latency_ms + streamed.latency_ms, 2),
            cost_usd=round(retry_response.cost_usd + streamed.cost_usd, 8),
            finish_reason=retry_response.finish_reason,
            fallback_used=retry_response.fallback_used or streamed.fallback_used,
            attempts=retry_response.attempts or streamed.attempts,
            raw=retry_response.raw,
        )
        return payload, combined, retries + 1

    def _log_unfinished(
        self,
        *,
        question: str,
        partial: str,
        response: LLMResponse | None,
        prompt_mode: str,
        thinking_level: str,
        started: float,
        prompt_ms: float,
        prompt_done_at: float,
        first_token_at: float | None,
        context: BuiltContext,
        chunks: Sequence[RetrievedChunk],
        query_type: str | None,
        retrieval_result: RetrievalResult | None,
        session_id: str | None,
        user_id: str | None,
        rewritten_query: str | None,
        conversation_tokens: int,
        prompt_audit: PromptAudit | None,
        status: str,
    ) -> None:
        finished_at = time.perf_counter()
        latency = (finished_at - started) * 1000
        ttft = (first_token_at - started) * 1000 if first_token_at else latency
        payload = AnswerPayload(
            answer=partial.strip() or "[chưa có nội dung]",
            reasoning_steps=[],
            citations=[],
            confidence=0.0,
            abstained=True,
            abstention_type="unknown",
        )
        result = self._result(
            question=question,
            payload=payload,
            response=response,
            prompt_mode=prompt_mode,
            thinking_level=thinking_level,
            latency_ms=latency,
            context=context,
            chunks=chunks,
            query_type=query_type,
            schema_retries=0,
            warnings=("Stream kết thúc trước khi hoàn tất.",),
            citation_report=check_citations(payload, (), ()),
            ttft_ms=ttft,
            streaming=True,
            status=status,
            conversation_tokens=conversation_tokens,
            prompt_audit=prompt_audit,
            timings_ms=self._timings(
                retrieval_result,
                prompt_ms=prompt_ms,
                prefill_ms=((first_token_at - prompt_done_at) * 1000 if first_token_at else 0.0),
                generation_ms=((finished_at - first_token_at) * 1000 if first_token_at else 0.0),
                ttft_ms=ttft,
                total_ms=latency,
                output_tokens=response.usage.output_tokens if response else 0,
            ),
        )
        self._write_log(
            result,
            session_id,
            retrieval_result,
            user_id=user_id,
            rewritten_query=rewritten_query,
        )

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

    def _timings(
        self,
        retrieval_result: RetrievalResult | None,
        *,
        prompt_ms: float,
        prefill_ms: float,
        generation_ms: float,
        ttft_ms: float,
        total_ms: float,
        output_tokens: int,
    ) -> dict[str, float]:
        retrieval = retrieval_result.timings_ms if retrieval_result else {}
        return {
            "retrieval_ms": round(float(retrieval.get("total_ms", 0.0)), 2),
            "rerank_ms": round(float(retrieval.get("rerank_ms", 0.0)), 2),
            "parent_expand_ms": round(float(retrieval.get("parent_ms", 0.0)), 2),
            "prompt_ms": round(prompt_ms, 2),
            "prefill_ms": round(prefill_ms, 2),
            "generation_ms": round(generation_ms, 2),
            "output_tokens": float(output_tokens),
            "ttft_ms": round(ttft_ms, 2),
            "total_ms": round(total_ms, 2),
        }

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
        ttft_ms: float = 0.0,
        streaming: bool = False,
        status: str = "complete",
        conversation_tokens: int = 0,
        prompt_audit: PromptAudit | None = None,
        timings_ms: dict[str, float] | None = None,
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
            extra={
                "provider_latency_ms": response.latency_ms if response else 0.0,
                "judge_provider": self.config.judge_provider,
                "prompt_audit": prompt_audit.as_dict() if prompt_audit is not None else None,
                "citations_enriched": enrich_citations(payload, context.blocks, chunks),
            },
            ttft_ms=round(ttft_ms, 2),
            streaming=streaming,
            status=status,
            conversation_tokens=conversation_tokens,
            timings_ms=dict(timings_ms or {}),
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
        *,
        user_id: str | None = None,
        rewritten_query: str | None = None,
    ) -> None:
        if self.log_writer is None:
            return
        query = rewritten_query
        if query is None and retrieval_result is not None:
            query = retrieval_result.normalized_query
        self.log_writer.write(
            result,
            session_id=session_id,
            rewritten_query=query,
            user_id=user_id,
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
