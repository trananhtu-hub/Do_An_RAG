from __future__ import annotations

import time
from dataclasses import dataclass
from uuid import UUID

from ..generation.providers import FallbackChain, LLMError
from ..sessions.types import MessageRecord, SessionRecord, SessionRepository
from .config import ConversationConfig
from .context import estimate_tokens, format_message
from .prompts import ConversationPromptLibrary

_SUMMARY_MAX_ITEMS = 6


@dataclass(frozen=True)
class SummaryResult:
    updated: bool
    summary: str | None
    source: str
    summarized_messages: int
    kept_messages: int
    latency_ms: float
    usage_tokens: int
    warning: str | None = None


class ConversationSummarizer:
    def __init__(
        self,
        config: ConversationConfig,
        chain: FallbackChain,
        prompts: ConversationPromptLibrary,
        repository: SessionRepository,
    ) -> None:
        self.config = config
        self.chain = chain
        self.prompts = prompts
        self.repository = repository

    def plan_summary(
        self,
        session: SessionRecord,
        messages: list[MessageRecord],
    ) -> tuple[list[MessageRecord], int] | None:
        """Trả về (tin nhắn cần tóm tắt, mốc giữ lại) khi đã vượt ngưỡng."""
        cfg = self.config.summary
        if not cfg.enabled or len(messages) <= cfg.keep_recent_turns * 2:
            return None
        start = max(0, min(session.summary_message_count, len(messages)))
        turns = sum(1 for message in messages[start:] if message.role == "user")
        tokens = sum(
            message.token_count
            or estimate_tokens(message.content, self.config.context.chars_per_token)
            for message in messages[start:]
        )
        if turns < cfg.trigger_turns and tokens < cfg.trigger_tokens:
            return None

        keep_count = cfg.keep_recent_turns * 2
        cut = len(messages) - keep_count
        while cut > start and messages[cut].role != "user":
            cut -= 1
        if cut - start < cfg.min_messages:
            return None
        to_summarize = messages[start:cut]
        if not to_summarize:
            return None
        return to_summarize, cut

    def is_due(self, session: SessionRecord, messages: list[MessageRecord]) -> bool:
        return self.plan_summary(session, messages) is not None

    def store_fallback(
        self,
        user_id: UUID,
        session: SessionRecord,
        messages: list[MessageRecord],
    ) -> SummaryResult | None:
        """Lưu ngay một bản tóm tắt tạm không gọi mô hình khi tóm tắt nền chưa xong.

        Bản tóm tắt của mô hình (nếu chạy nền xong) sẽ ghi đè bản tạm này với cùng mốc.
        """
        plan = self.plan_summary(session, messages)
        if plan is None:
            return None
        to_summarize, cut = plan
        started = time.perf_counter()
        summary = _fallback_summary(session.summary, to_summarize)
        summary = _truncate_summary(summary, self._summary_max_chars())
        updated = self.repository.set_summary(
            user_id,
            session.id,
            summary=summary,
            summary_message_count=cut,
        )
        return SummaryResult(
            updated=updated is not None,
            summary=summary,
            source="inline_fallback",
            summarized_messages=len(to_summarize),
            kept_messages=len(messages) - cut,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            usage_tokens=0,
        )

    def _summary_max_chars(self) -> int:
        cfg = self.config.summary
        return max(400, int(cfg.max_summary_tokens * self.config.context.chars_per_token))

    def maybe_summarize(
        self,
        user_id: UUID,
        session: SessionRecord,
        messages: list[MessageRecord],
        *,
        timeout_ms: int | None = None,
    ) -> SummaryResult | None:
        cfg = self.config.summary
        plan = self.plan_summary(session, messages)
        if plan is None:
            return None
        to_summarize, cut = plan

        started = time.perf_counter()
        message_text = "\n".join(
            format_message(message, max_chars=self.config.context.max_message_chars)
            for message in to_summarize
        )
        max_words = max(80, int(cfg.max_summary_tokens * 0.7))
        prompt_messages = self.prompts.summary_messages(
            previous_summary=session.summary,
            messages=message_text,
            max_words=max_words,
        )
        source = "llm"
        usage_tokens = 0
        warning: str | None = None
        try:
            response = self.chain.complete(
                prompt_messages,
                thinking_level=cfg.thinking_level,
                max_output_tokens=cfg.max_output_tokens,
                json_mode=False,
                timeout_ms=timeout_ms or cfg.timeout_ms,
            )
            usage_tokens = response.usage.input_tokens + response.usage.output_tokens
            summary = _clean_summary(response.text)
            if not summary:
                raise LLMError("Mô hình trả tóm tắt rỗng", provider=response.provider)
        except LLMError as exc:
            source = "fallback"
            warning = f"Không tóm tắt được bằng mô hình: {exc}"
            summary = _fallback_summary(session.summary, to_summarize)

        summary = _truncate_summary(summary, self._summary_max_chars())
        updated = self.repository.set_summary(
            user_id,
            session.id,
            summary=summary,
            summary_message_count=cut,
        )
        return SummaryResult(
            updated=updated is not None,
            summary=summary,
            source=source,
            summarized_messages=len(to_summarize),
            kept_messages=len(messages) - cut,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            usage_tokens=usage_tokens,
            warning=warning,
        )


def _truncate_summary(summary: str, max_chars: int) -> str:
    if len(summary) > max_chars:
        return summary[:max_chars].rstrip() + "…"
    return summary


def _clean_summary(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("markdown"):
            cleaned = cleaned[len("markdown") :].strip()
    return cleaned[:4000]


def _fallback_summary(previous: str | None, messages: list[MessageRecord]) -> str:
    lines: list[str] = []
    if previous and previous.strip():
        lines.append(previous.strip()[:1200])
    lines.append("Tóm tắt tạm (mô hình tóm tắt không khả dụng):")
    pairs = messages[-_SUMMARY_MAX_ITEMS:]
    for message in pairs:
        prefix = "Hỏi" if message.role == "user" else "Đáp"
        text = message.content.strip().replace("\n", " ")
        lines.append(f"- {prefix}: {text[:180]}")
    return "\n".join(lines)
