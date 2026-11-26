from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from .conversation import (
    CondensationResult,
    ConversationConfig,
    ConversationContext,
    ConversationPromptLibrary,
    ConversationSummarizer,
    QueryCondenser,
    build_conversation_context,
    estimate_tokens,
    load_conversation_config,
)
from .generation.providers import FallbackChain, LLMError
from .generation.service import GenerationService
from .generation.service import get_service as get_generation_service
from .generation.types import GenerationResult
from .sessions.types import (
    MessageRecord,
    SessionNotFound,
    SessionRecord,
    SessionRepository,
    SessionStoreError,
)

_LOGGER = logging.getLogger(__name__)
_HISTORY_MESSAGES = 80


@dataclass(frozen=True)
class ChatOptions:
    """Tùy chọn người dùng cho một lượt hỏi.

    ``mode=None`` giữ nguyên hành vi cũ (tự chọn prompt theo loại câu hỏi);
    giao diện luôn gửi rõ ``fast`` hoặc ``step_by_step``.
    """

    mode: str | None = None
    language: str | None = None
    model: str | None = None

    @property
    def use_cot(self) -> bool:
        return self.mode != "fast"

    @property
    def thinking_level(self) -> str | None:
        return "none" if self.mode == "fast" else None

    @property
    def extra_instruction(self) -> str | None:
        if self.language == "en":
            return (
                "Người học chọn trả lời bằng tiếng Anh: viết phần answer bằng tiếng Anh, "
                "giữ nguyên thuật ngữ AWS và định dạng trích dẫn [tài liệu – mục Y]."
            )
        return None


@dataclass(frozen=True)
class StreamEvent:
    event: str
    data: dict[str, Any]


@dataclass(frozen=True)
class SummaryRefresh:
    source: str
    latency_ms: float


@dataclass(frozen=True)
class PreparedTurn:
    user_id: UUID
    session: SessionRecord
    question: str
    rewritten: str
    condensation: CondensationResult
    conversation: ConversationContext
    user_message: MessageRecord | None = None
    assistant_message: MessageRecord | None = None
    replay: MessageRecord | None = None
    prepare_ms: float = 0.0
    summary_source: str | None = None
    summary_latency_ms: float = 0.0
    options: ChatOptions = field(default_factory=ChatOptions)

    @property
    def is_replay(self) -> bool:
        return self.replay is not None


@dataclass(frozen=True)
class ChatAnswer:
    session_id: UUID
    message: MessageRecord | None
    result: GenerationResult | None
    turn: PreparedTurn
    replayed: bool = False


class ChatService:
    """Ghép phiên hội thoại, viết lại câu hỏi, tóm tắt và tầng sinh câu trả lời."""

    def __init__(
        self,
        repository: SessionRepository,
        generation: GenerationService,
        config: ConversationConfig,
        *,
        condenser: QueryCondenser | None = None,
        summarizer: ConversationSummarizer | None = None,
    ) -> None:
        self.repository = repository
        self.generation = generation
        self.config = config
        prompts = ConversationPromptLibrary(config.prompt_root)
        chain: FallbackChain = generation.chain
        self.condenser = condenser or QueryCondenser(config.condensation, chain, prompts)
        self.summarizer = summarizer or ConversationSummarizer(config, chain, prompts, repository)
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, config.summary.workers),
            thread_name_prefix="conversation-summary",
        )
        self._summary_lock = threading.Lock()
        self._summary_inflight: set[UUID] = set()
        self._summary_pending: set[UUID] = set()
        self._summary_futures: dict[UUID, Future[Any]] = {}

    # -- phiên ---------------------------------------------------------------
    def create_session(
        self,
        user_id: UUID,
        *,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionRecord:
        return self.repository.create_session(user_id, title=title, metadata=metadata)

    def list_sessions(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[SessionRecord]:
        return self.repository.list_sessions(user_id, limit=limit, offset=offset)

    def count_sessions(self, user_id: UUID) -> int:
        return self.repository.count_sessions(user_id)

    def get_session(self, user_id: UUID, session_id: UUID) -> SessionRecord:
        session = self.repository.get_session(user_id, session_id)
        if session is None:
            raise SessionNotFound("Phiên không tồn tại hoặc không thuộc người dùng hiện tại.")
        return session

    def rename_session(self, user_id: UUID, session_id: UUID, title: str) -> SessionRecord | None:
        return self.repository.update_session(user_id, session_id, title=title)

    def delete_session(self, user_id: UUID, session_id: UUID) -> bool:
        return self.repository.delete_session(user_id, session_id)

    def delete_all_sessions(self, user_id: UUID) -> int:
        return self.repository.delete_all_sessions(user_id)

    def list_messages(
        self, user_id: UUID, session_id: UUID, *, limit: int = 200, offset: int = 0
    ) -> list[MessageRecord]:
        self.get_session(user_id, session_id)
        return self.repository.list_messages(user_id, session_id, limit=limit, offset=offset)

    # -- một lượt ------------------------------------------------------------
    def prepare(
        self,
        user_id: UUID,
        session_id: UUID,
        question: str,
        *,
        request_id: UUID | None = None,
        options: ChatOptions | None = None,
    ) -> PreparedTurn:
        started = time.perf_counter()
        options = options or ChatOptions()
        session = self.get_session(user_id, session_id)
        question = question.strip()
        if not question:
            raise ValueError("Câu hỏi rỗng")

        if request_id is not None:
            existing = self.repository.get_message_by_request(user_id, session_id, request_id)
            if existing is not None:
                return self._prepare_existing(session, question, existing, started, options=options)

        session, summary_refresh = self._refresh_summary(user_id, session_id, session)
        history = _trim_after_topic_shift(
            self._history(user_id, session_id, start=session.summary_message_count)
        )
        condensation = self.condenser.condense(
            question,
            _pairs(history),
            summary=session.summary,
        )
        conversation = self._conversation_context(session, history, condensation)
        metadata = {
            "stream_status": "pending",
            "rewrite_source": condensation.source,
            "depends_on_context": condensation.depends_on_context,
            "condensation_latency_ms": condensation.latency_ms,
            "conversation_tokens": conversation.tokens,
            "summary_source": summary_refresh.source if summary_refresh else None,
            "summary_latency_ms": summary_refresh.latency_ms if summary_refresh else 0.0,
        }
        try:
            pair = self.repository.begin_turn(
                user_id,
                session_id,
                question=question,
                rewritten_query=condensation.rewritten,
                question_tokens=estimate_tokens(question, self.config.context.chars_per_token),
                request_id=request_id,
                assistant_metadata=metadata,
            )
        except SessionStoreError:
            if request_id is not None:
                existing = self.repository.get_message_by_request(user_id, session_id, request_id)
                if existing is not None:
                    return self._prepare_existing(
                        session, question, existing, started, options=options
                    )
            raise
        if pair is None:
            raise SessionNotFound("Phiên không tồn tại hoặc không thuộc người dùng hiện tại.")
        user_message, assistant_message = pair
        if condensation.source == "topic_shift":
            try:
                # Đổi chủ đề: bỏ tóm tắt cũ và dời mốc lịch sử để các lượt sau
                # không kéo nội dung chủ đề trước vào ngữ cảnh.
                self.repository.set_summary(
                    user_id,
                    session_id,
                    summary="",
                    summary_message_count=session.message_count,
                )
            except SessionStoreError:
                _LOGGER.warning("Không đặt lại được tóm tắt khi đổi chủ đề")
        return PreparedTurn(
            user_id=user_id,
            session=self.repository.get_session(user_id, session_id) or session,
            question=question,
            rewritten=condensation.rewritten,
            condensation=condensation,
            conversation=conversation,
            user_message=user_message,
            assistant_message=assistant_message,
            prepare_ms=round((time.perf_counter() - started) * 1000, 2),
            summary_source=summary_refresh.source if summary_refresh else None,
            summary_latency_ms=summary_refresh.latency_ms if summary_refresh else 0.0,
            options=options,
        )

    def _prepare_existing(
        self,
        session: SessionRecord,
        question: str,
        existing: MessageRecord,
        started: float,
        *,
        options: ChatOptions | None = None,
    ) -> PreparedTurn:
        if _is_complete(existing):
            return PreparedTurn(
                user_id=session.user_id,
                session=session,
                question=question,
                rewritten=(existing.metadata or {}).get("rewritten_query") or question,
                condensation=CondensationResult(
                    original=question,
                    rewritten=(existing.metadata or {}).get("rewritten_query") or question,
                    source="replay",
                    depends_on_context=False,
                    latency_ms=0.0,
                    usage_tokens=0,
                ),
                conversation=ConversationContext("", 0, 0, False, False),
                assistant_message=existing,
                replay=existing,
                prepare_ms=round((time.perf_counter() - started) * 1000, 2),
                options=options or ChatOptions(),
            )
        raw = self.repository.list_messages(
            session.user_id,
            session.id,
            limit=_HISTORY_MESSAGES + 4,
            offset=max(0, session.summary_message_count),
        )
        index = next((i for i, message in enumerate(raw) if message.id == existing.id), None)
        before = raw[:index] if index is not None else raw
        user_message = before[-1] if before and before[-1].role == "user" else None
        history = _trim_after_topic_shift(
            [
                message
                for message in (before[:-1] if user_message else before)
                if message.content.strip()
            ]
        )
        rewritten = (user_message.rewritten_query if user_message else None) or question
        source = (existing.metadata or {}).get("rewrite_source", "saved")
        condensation = CondensationResult(
            original=question,
            rewritten=rewritten,
            source=str(source),
            depends_on_context=bool((existing.metadata or {}).get("depends_on_context", False)),
            latency_ms=0.0,
            usage_tokens=0,
        )
        conversation = self._conversation_context(session, history, condensation)
        return PreparedTurn(
            user_id=session.user_id,
            session=session,
            question=question,
            rewritten=rewritten,
            condensation=condensation,
            conversation=conversation,
            user_message=user_message,
            assistant_message=existing,
            prepare_ms=round((time.perf_counter() - started) * 1000, 2),
            options=options or ChatOptions(),
        )

    def answer(
        self,
        user_id: UUID,
        session_id: UUID,
        question: str,
        *,
        request_id: UUID | None = None,
        options: ChatOptions | None = None,
    ) -> ChatAnswer:
        turn = self.prepare(user_id, session_id, question, request_id=request_id, options=options)
        if turn.replay is not None:
            return ChatAnswer(session_id, turn.replay, None, turn, replayed=True)
        try:
            result = self.generation.answer(
                turn.rewritten,
                session_id=str(session_id),
                user_id=str(user_id),
                rewritten_query=turn.rewritten,
                conversation=turn.conversation.text or None,
                conversation_tokens=turn.conversation.tokens,
                use_cot=turn.options.use_cot,
                thinking_level=turn.options.thinking_level,
                extra_instruction=turn.options.extra_instruction,
            )
        except LLMError as exc:
            self._finalize(turn, content="", status="error", error=str(exc))
            raise
        message = self._finalize(
            turn, content=result.payload.answer, status="complete", result=result
        )
        return ChatAnswer(session_id, message, result, turn)

    def stream(
        self,
        user_id: UUID,
        session_id: UUID,
        question: str,
        *,
        request_id: UUID | None = None,
        options: ChatOptions | None = None,
    ) -> Iterator[StreamEvent]:
        turn = self.prepare(user_id, session_id, question, request_id=request_id, options=options)
        yield from self.stream_turn(turn)

    def stream_turn(self, turn: PreparedTurn) -> Iterator[StreamEvent]:
        started = time.perf_counter()
        yield StreamEvent("meta", self._meta_data(turn))

        if turn.replay is not None:
            for piece in _chunks(turn.replay.content):
                yield StreamEvent("token", {"text": piece})
            yield StreamEvent(
                "citations",
                {
                    "items": list(turn.replay.citations),
                    "citation_validity": (turn.replay.metadata or {}).get("citation_validity", 1.0),
                    "warnings": [],
                },
            )
            yield StreamEvent(
                "done",
                {
                    "session_id": str(turn.session.id),
                    "message_id": str(turn.replay.id),
                    "status": "complete",
                    "replayed": True,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            return

        partial: list[str] = []
        result: GenerationResult | None = None
        iterator = self.generation.answer_stream(
            turn.rewritten,
            session_id=str(turn.session.id),
            user_id=str(turn.user_id),
            rewritten_query=turn.rewritten,
            conversation=turn.conversation.text or None,
            conversation_tokens=turn.conversation.tokens,
            use_cot=turn.options.use_cot,
            thinking_level=turn.options.thinking_level,
            extra_instruction=turn.options.extra_instruction,
        )
        try:
            try:
                for delta in iterator:
                    if delta.text:
                        partial.append(delta.text)
                        yield StreamEvent("token", {"text": delta.text})
                    if delta.result is not None:
                        result = delta.result
            except GeneratorExit:
                self._finalize(
                    turn,
                    content="".join(partial),
                    status="interrupted",
                )
                raise
            except LLMError as exc:
                message = self._finalize(
                    turn,
                    content="".join(partial),
                    status="error",
                    error=str(exc),
                )
                yield StreamEvent(
                    "error",
                    {
                        "code": "generation_failed",
                        "message": (
                            "Không tạo được câu trả lời từ mô hình. Bạn thử lại sau ít phút."
                        ),
                        "message_id": str(message.id) if message else None,
                    },
                )
                yield StreamEvent(
                    "done",
                    {
                        "session_id": str(turn.session.id),
                        "message_id": str(message.id) if message else None,
                        "status": "error",
                        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                )
                return
        finally:
            iterator.close()

        if result is None:
            message = self._finalize(
                turn,
                content="".join(partial),
                status="error",
                error="Không nhận được kết quả cuối từ tầng sinh.",
            )
            yield StreamEvent(
                "error",
                {
                    "code": "empty_result",
                    "message": "Mô hình không trả kết quả.",
                    "message_id": str(message.id) if message else None,
                },
            )
            return

        message = self._finalize(
            turn, content=result.payload.answer, status="complete", result=result
        )
        yield StreamEvent("citations", self._citations_data(result))
        yield StreamEvent("done", self._done_data(turn, result, message, started))

    # -- dữ liệu sự kiện -----------------------------------------------------
    def _meta_data(self, turn: PreparedTurn) -> dict[str, Any]:
        return {
            "session_id": str(turn.session.id),
            "user_message_id": str(turn.user_message.id) if turn.user_message else None,
            "message_id": (str(turn.assistant_message.id) if turn.assistant_message else None),
            "question": turn.question,
            "rewritten_query": turn.rewritten,
            "rewrite_source": turn.condensation.source,
            "depends_on_context": turn.condensation.depends_on_context,
            "conversation_tokens": turn.conversation.tokens,
            "conversation_messages": turn.conversation.message_count,
            "summary_used": turn.conversation.summary_used,
            "summary_source": turn.summary_source,
            "summary_latency_ms": turn.summary_latency_ms,
            "replayed": turn.is_replay,
            "prepare_ms": turn.prepare_ms,
            "answer_mode": turn.options.mode or "auto",
            "answer_language": turn.options.language or "vi",
        }

    @staticmethod
    def _citations_data(result: GenerationResult) -> dict[str, Any]:
        items = result.extra.get("citations_enriched")
        if not isinstance(items, list):
            items = [citation.model_dump() for citation in result.payload.citations]
        return {
            "items": items,
            "citation_validity": result.citation_report.citation_validity,
            "unmatched": [
                {"citation": issue.citation, "reason": issue.reason}
                for issue in result.citation_report.unmatched
            ],
            "warnings": list(result.warnings),
        }

    def _done_data(
        self,
        turn: PreparedTurn,
        result: GenerationResult,
        message: MessageRecord | None,
        started: float,
    ) -> dict[str, Any]:
        return {
            "session_id": str(turn.session.id),
            "message_id": str(message.id) if message else None,
            "status": result.status,
            "replayed": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "ttft_ms": result.ttft_ms,
            "usage": {
                "input_tokens": result.usage_input_tokens,
                "output_tokens": result.usage_output_tokens,
            },
            "provider": result.provider,
            "model": result.model,
            "fallback_used": result.fallback_used,
            "confidence": result.payload.confidence,
            "abstained": result.payload.abstained,
            "abstention_type": result.payload.abstention_type,
            "prompt_audit": result.extra.get("prompt_audit"),
            "timings_ms": result.timings_ms,
        }

    # -- lưu kết quả ---------------------------------------------------------
    def _finalize(
        self,
        turn: PreparedTurn,
        *,
        content: str,
        status: str,
        result: GenerationResult | None = None,
        error: str | None = None,
    ) -> MessageRecord | None:
        if turn.assistant_message is None:
            return None
        stored = content.strip()
        if not stored and status != "complete":
            stored = (
                "(Câu trả lời đã bị ngắt khi đang tạo.)"
                if status == "interrupted"
                else "(Không tạo được câu trả lời.)"
            )
        metadata: dict[str, Any] = {
            "stream_status": status,
            "rewrite_source": turn.condensation.source,
            "depends_on_context": turn.condensation.depends_on_context,
            "rewritten_query": turn.rewritten,
            "conversation_tokens": turn.conversation.tokens,
            "conversation_messages": turn.conversation.message_count,
            "summary_used": turn.conversation.summary_used,
            "summary_source": turn.summary_source,
            "summary_latency_ms": turn.summary_latency_ms,
            "answer_mode": turn.options.mode or "auto",
            "answer_language": turn.options.language or "vi",
        }
        citations: list[dict[str, Any]] = []
        if result is not None:
            enriched = result.extra.get("citations_enriched")
            citations = (
                enriched
                if isinstance(enriched, list)
                else [citation.model_dump() for citation in result.payload.citations]
            )
            metadata.update(
                {
                    "provider": result.provider,
                    "model": result.model,
                    "fallback_used": result.fallback_used,
                    "latency_ms": result.latency_ms,
                    "ttft_ms": result.ttft_ms,
                    "confidence": result.payload.confidence,
                    "abstained": result.payload.abstained,
                    "abstention_type": result.payload.abstention_type,
                    "citation_validity": result.citation_report.citation_validity,
                    "warnings": list(result.warnings),
                    "prompt_audit": result.extra.get("prompt_audit"),
                    "timings_ms": result.timings_ms,
                }
            )
        if error:
            metadata["error"] = error[:1000]
        message = self.repository.update_message(
            turn.user_id,
            turn.assistant_message.id,
            content=stored,
            citations=citations,
            metadata=metadata,
            token_count=estimate_tokens(stored, self.config.context.chars_per_token),
        )
        if status == "complete":
            self._schedule_summary(turn.user_id, turn.session.id)
        return message

    # -- tóm tắt nền ---------------------------------------------------------
    def _refresh_summary(
        self, user_id: UUID, session_id: UUID, session: SessionRecord
    ) -> tuple[SessionRecord, SummaryRefresh | None]:
        """Bảo đảm tóm tắt mới nhất được dùng ngay ở lượt kế tiếp khi đã tới hạn.

        Chờ tác vụ tóm tắt nền tối đa ``summary.await_ms``; nếu vẫn chưa xong thì
        lưu ngay một bản tóm tắt tạm (không gọi mô hình) để lượt này dùng được.
        """
        cfg = self.config.summary
        if not cfg.enabled:
            return session, None
        started = time.perf_counter()
        completed = self._await_summary(session_id, cfg.await_ms)
        refreshed = self.repository.get_session(user_id, session_id) or session
        latency = round((time.perf_counter() - started) * 1000, 2)
        if completed and (refreshed.summary or "").strip():
            return refreshed, SummaryRefresh("stored", latency)
        if not self._summary_possible(refreshed):
            return refreshed, None
        messages = self.repository.list_messages(user_id, session_id, limit=500)
        if not self.summarizer.is_due(refreshed, messages):
            return refreshed, None
        running = self._summary_running(session_id)
        if running:
            outcome = self.summarizer.store_fallback(user_id, refreshed, messages)
        else:
            outcome = self.summarizer.maybe_summarize(
                user_id, refreshed, messages, timeout_ms=cfg.await_ms
            )
        if outcome is None or not outcome.updated:
            return refreshed, None
        refreshed = self.repository.get_session(user_id, session_id) or refreshed
        source = outcome.source if running else f"inline_{outcome.source}"
        return refreshed, SummaryRefresh(source, round((time.perf_counter() - started) * 1000, 2))

    def _summary_possible(self, session: SessionRecord) -> bool:
        """Kiểm tra rẻ để bỏ qua truy vấn tin nhắn khi chắc chắn chưa tới hạn."""
        cfg = self.config.summary
        if session.message_count <= cfg.keep_recent_turns * 2:
            return False
        pending = session.message_count - session.summary_message_count
        return pending >= cfg.trigger_turns or session.token_count >= cfg.trigger_tokens

    def _summary_running(self, session_id: UUID) -> bool:
        with self._summary_lock:
            return session_id in self._summary_inflight

    def _await_summary(self, session_id: UUID, timeout_ms: int) -> bool:
        """Chờ tối đa ``timeout_ms`` cho chuỗi tác vụ tóm tắt của phiên.

        Trả về True khi không còn tác vụ nào đang chạy.
        """
        deadline = time.monotonic() + max(0.0, timeout_ms / 1000.0)
        while True:
            with self._summary_lock:
                future = self._summary_futures.get(session_id)
            if future is None:
                return True
            remaining = deadline - time.monotonic()
            if remaining > 0 and not future.done():
                try:
                    future.result(timeout=remaining)
                except Exception:  # noqa: BLE001 - lỗi đã log trong luồng nền
                    pass
            if not future.done():
                return False
            with self._summary_lock:
                current = self._summary_futures.get(session_id)
            if current is None or current is future:
                return True

    def _schedule_summary(self, user_id: UUID, session_id: UUID) -> None:
        if not self.config.summary.enabled:
            return
        with self._summary_lock:
            if session_id in self._summary_inflight:
                # Lượt mới đến khi lượt tóm tắt cũ chưa xong: hẹn chạy lại sau.
                self._summary_pending.add(session_id)
                return
            self._summary_inflight.add(session_id)
            self._summary_futures = {
                key: item for key, item in self._summary_futures.items() if not item.done()
            }
            self._summary_futures[session_id] = self._executor.submit(
                self._run_summary, user_id, session_id
            )

    def _run_summary(self, user_id: UUID, session_id: UUID) -> None:
        try:
            session = self.repository.get_session(user_id, session_id)
            if session is None:
                return
            messages = self.repository.list_messages(user_id, session_id, limit=500)
            outcome = self.summarizer.maybe_summarize(user_id, session, messages)
            if outcome is not None and outcome.updated:
                _LOGGER.info(
                    "Đã cập nhật tóm tắt phiên %s (%s tin nhắn, nguồn %s, %.0f ms)",
                    session_id,
                    outcome.summarized_messages,
                    outcome.source,
                    outcome.latency_ms,
                )
        except Exception as exc:  # noqa: BLE001 - tóm tắt nền không được làm sập request
            _LOGGER.warning("Không tóm tắt được phiên %s: %s", session_id, type(exc).__name__)
        finally:
            with self._summary_lock:
                self._summary_inflight.discard(session_id)
                pending = session_id in self._summary_pending
                self._summary_pending.discard(session_id)
        if pending:
            self._schedule_summary(user_id, session_id)

    def wait_for_background(self, timeout: float = 30.0) -> None:
        deadline = time.monotonic() + timeout
        while True:
            with self._summary_lock:
                futures = list(self._summary_futures.values())
            for future in futures:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                try:
                    future.result(timeout=remaining)
                except Exception:  # noqa: BLE001 - đã log trong luồng nền
                    pass
            with self._summary_lock:
                changed = list(self._summary_futures.values()) != futures
                if not changed and not self._summary_inflight:
                    return
            if time.monotonic() >= deadline:
                return

    # -- tiện ích ------------------------------------------------------------
    def _conversation_context(
        self,
        session: SessionRecord,
        history: list[MessageRecord],
        condensation: CondensationResult,
    ) -> ConversationContext:
        if condensation.source == "topic_shift":
            return build_conversation_context(
                summary=None,
                messages=[],
                config=self.config.context,
            )
        return build_conversation_context(
            summary=session.summary,
            messages=history,
            config=self.config.context,
        )

    def _history(
        self,
        user_id: UUID,
        session_id: UUID,
        *,
        start: int = 0,
        limit: int = _HISTORY_MESSAGES,
    ) -> list[MessageRecord]:
        messages = self.repository.list_messages(
            user_id, session_id, limit=limit, offset=max(0, start)
        )
        return [message for message in messages if message.content.strip()]

    def close(self) -> None:
        self.wait_for_background(timeout=5.0)
        self._executor.shutdown(wait=False, cancel_futures=True)


def _pairs(messages: list[MessageRecord]) -> list[tuple[str, str]]:
    return [(message.role, message.content) for message in messages if message.role != "system"]


def _trim_after_topic_shift(messages: list[MessageRecord]) -> list[MessageRecord]:
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        metadata = message.metadata or {}
        if message.role == "assistant" and metadata.get("rewrite_source") == "topic_shift":
            start = index - 1 if index > 0 and messages[index - 1].role == "user" else index
            return messages[start:]
    return messages


def _is_complete(message: MessageRecord) -> bool:
    if not message.content.strip():
        return False
    return (message.metadata or {}).get("stream_status", "complete") == "complete"


def _chunks(text: str, size: int = 64) -> list[str]:
    if not text:
        return []
    return [text[index : index + size] for index in range(0, len(text), size)]


_chat_service: ChatService | None = None
_chat_lock = threading.Lock()


def build_chat_service(repository: SessionRepository | None = None) -> ChatService:
    from app.api.deps import get_session_repository

    config = load_conversation_config()
    generation = get_generation_service()
    return ChatService(
        repository or get_session_repository(),
        generation,
        config,
    )


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        with _chat_lock:
            if _chat_service is None:
                _chat_service = build_chat_service()
    return _chat_service


def set_chat_service(service: ChatService | None) -> None:
    global _chat_service
    with _chat_lock:
        if _chat_service is not None and _chat_service is not service:
            _chat_service.close()
        _chat_service = service
