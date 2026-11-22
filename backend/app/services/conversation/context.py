from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from .config import ConversationContextConfig

SUMMARY_HEADER = "# TÓM TẮT HỘI THOẠI TRƯỚC ĐÓ"
RECENT_HEADER = "# CÁC LƯỢT GẦN NHẤT"


class _Message(Protocol):
    role: str
    content: str


@dataclass(frozen=True)
class ConversationContext:
    text: str
    tokens: int
    message_count: int
    summary_used: bool
    trimmed: bool

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


def estimate_tokens(text: str, chars_per_token: float) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / max(chars_per_token, 0.1)))


def label_for(role: str) -> str:
    if role == "user":
        return "Người học"
    if role == "assistant":
        return "Trợ lý"
    return "Hệ thống"


def format_message(message: _Message, *, max_chars: int) -> str:
    content = message.content.strip()
    if len(content) > max_chars:
        content = content[:max_chars].rstrip() + "…"
    return f"[{label_for(message.role)}] {content}"


def format_history(messages: list[_Message], *, max_chars: int) -> str:
    return "\n".join(format_message(message, max_chars=max_chars) for message in messages)


def build_conversation_context(
    *,
    summary: str | None,
    messages: list[_Message],
    config: ConversationContextConfig,
) -> ConversationContext:
    """Dựng ngữ cảnh hội thoại trong ngân sách token, ưu tiên tóm tắt và lượt mới nhất."""
    budget = max(1, int(config.max_conversation_tokens * config.chars_per_token))
    summary_text = (summary or "").strip()
    if summary_text:
        cap = max(200, int(budget * 0.45))
        if len(summary_text) > cap:
            summary_text = summary_text[:cap].rstrip() + "…"
    selected: list[str] = []
    # Trừ sẵn phần tiêu đề và dấu ngăn cách để tổng văn bản không vượt ngân sách.
    remaining = budget - (len(RECENT_HEADER) + 3)
    trimmed = False
    if summary_text:
        remaining -= len(SUMMARY_HEADER) + len(summary_text) + 3
    for message in reversed(messages):
        block = format_message(message, max_chars=config.max_message_chars)
        if remaining <= 0:
            trimmed = True
            break
        if len(block) > remaining:
            if selected:
                trimmed = True
                break
            block = block[:remaining].rstrip()
            trimmed = True
        selected.append(block)
        remaining -= len(block) + 1
    selected.reverse()

    parts: list[str] = []
    if summary_text:
        parts.append(f"{SUMMARY_HEADER}\n{summary_text}")
    if selected:
        parts.append(f"{RECENT_HEADER}\n" + "\n".join(selected))
    text = "\n\n".join(parts).strip()
    return ConversationContext(
        text=text,
        tokens=estimate_tokens(text, config.chars_per_token),
        message_count=len(selected),
        summary_used=bool(summary_text),
        trimmed=trimmed,
    )
