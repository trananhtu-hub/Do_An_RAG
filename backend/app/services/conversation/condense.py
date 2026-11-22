from __future__ import annotations

import re
import time
from dataclasses import dataclass

from ..generation.providers import FallbackChain, LLMError
from ..generation.schema import SchemaError, extract_json_object
from .config import CondensationConfig
from .context import format_history
from .prompts import ConversationPromptLibrary

_DEPENDENT = re.compile(
    r"\b("
    r"nó|này|đó|kia|ấy|vậy|thế|như trên|ở trên|trước đó|vừa nêu|vừa hỏi|"
    r"cả hai|hai dịch vụ|hai giải pháp|hai phương án|dịch vụ này|giải pháp này|"
    r"phương án này|cách này|cái này|trường hợp này|tình huống này|còn nếu|còn khi|"
    r"ngoài ra|thêm nữa|tại sao lại|vì sao lại|lúc đó|khi đó|điều này|ý này|"
    r"so với|khác ở đâu|khác gì|khác nhau|cái nào|loại nào|lớp nào|dịch vụ nào|"
    r"giải pháp nào|phương án nào|cách nào|hình thức nào|khi nào|thì sao|ra sao|"
    r"thế nào|bao lâu|bao nhiêu|ở đâu|vì sao|sao không|quay lại|ý bạn|bạn nói|"
    r"như vậy|vậy thì|vậy còn|còn"
    r")\b",
    re.IGNORECASE,
)

_TOPIC_SHIFT = re.compile(
    r"\b(đổi chủ đề|chủ đề khác|sang chủ đề|câu hỏi mới|bỏ qua phần|không liên quan)\b",
    re.IGNORECASE,
)

_TOPIC_SHIFT_PREFIX = re.compile(
    r"^\s*(?:đổi chủ đề|chủ đề khác|sang chủ đề|câu hỏi mới|bỏ qua phần|không liên quan)"
    r"\s*[:\-–,]?\s*",
    re.IGNORECASE,
)

_WORD = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class CondensationResult:
    original: str
    rewritten: str
    source: str
    depends_on_context: bool
    latency_ms: float
    usage_tokens: int
    warning: str | None = None

    @property
    def changed(self) -> bool:
        return _normalize(self.rewritten) != _normalize(self.original)

    @property
    def standalone(self) -> bool:
        return not self.depends_on_context


class QueryCondenser:
    def __init__(
        self,
        config: CondensationConfig,
        chain: FallbackChain,
        prompts: ConversationPromptLibrary,
    ) -> None:
        self.config = config
        self.chain = chain
        self.prompts = prompts

    def condense(
        self,
        question: str,
        history: list[tuple[str, str]],
        *,
        summary: str | None = None,
    ) -> CondensationResult:
        started = time.perf_counter()
        question = question.strip()
        if not self.config.enabled or not history:
            return self._result(question, question, "none", False, started)
        if _TOPIC_SHIFT.search(question):
            cleaned = _TOPIC_SHIFT_PREFIX.sub("", question).strip() or question
            return self._result(question, cleaned, "topic_shift", False, started)
        if not _needs_context(question):
            return self._result(question, question, "none", False, started)

        recent = history[-self.config.history_turns * 2 :]
        history_text = format_history(
            [_Pair(role, content) for role, content in recent],
            max_chars=800,
        )
        if summary:
            history_text = f"Tóm tắt trước đó: {summary.strip()[:1200]}\n{history_text}"
        messages = self.prompts.rewrite_messages(history=history_text, question=question)
        try:
            response = self.chain.complete(
                messages,
                thinking_level=self.config.thinking_level,
                max_output_tokens=self.config.max_output_tokens,
                json_mode=True,
                timeout_ms=self.config.timeout_ms,
            )
        except LLMError as exc:
            return self._fallback(question, history, started, f"Không viết lại được câu hỏi: {exc}")

        try:
            data = extract_json_object(response.text)
        except SchemaError:
            return self._fallback(
                question, history, started, "Mô hình viết lại trả JSON không hợp lệ."
            )

        rewritten = str(data.get("rewritten") or "").strip()
        depends = bool(data.get("depends_on_context", True))
        if not rewritten or len(rewritten) > self.config.max_rewrite_chars:
            return self._fallback(
                question, history, started, "Mô hình viết lại trả câu hỏi rỗng hoặc quá dài."
            )
        if not depends:
            rewritten = question
        return CondensationResult(
            original=question,
            rewritten=rewritten,
            source="llm",
            depends_on_context=depends,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            usage_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )

    def _fallback(
        self,
        question: str,
        history: list[tuple[str, str]],
        started: float,
        warning: str,
    ) -> CondensationResult:
        last_question = next(
            (content for role, content in reversed(history) if role == "user" and content.strip()),
            None,
        )
        if last_question:
            rewritten = (
                f"{question} (đặt trong ngữ cảnh câu hỏi trước: " f"{last_question.strip()[:300]})"
            )
        else:
            rewritten = question
        return self._result(question, rewritten, "fallback", True, started, warning=warning)

    @staticmethod
    def _result(
        original: str,
        rewritten: str,
        source: str,
        depends: bool,
        started: float,
        *,
        warning: str | None = None,
    ) -> CondensationResult:
        return CondensationResult(
            original=original,
            rewritten=rewritten,
            source=source,
            depends_on_context=depends,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            usage_tokens=0,
            warning=warning,
        )


class _Pair:
    __slots__ = ("role", "content")

    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content


def _needs_context(question: str) -> bool:
    if _DEPENDENT.search(question):
        return True
    # Câu hỏi đúng/sai ("... không?") thường bỏ chủ thể đang bàn ở lượt trước.
    if question.rstrip().endswith("không?"):
        return True
    # Câu ngắn thường bỏ chủ thể; gọi mô hình viết lại để khôi phục chủ thể từ hội thoại.
    return len(_WORD.findall(question)) < 9


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().casefold())
