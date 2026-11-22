from __future__ import annotations

from pathlib import Path

from ..generation.providers import LLMMessage

SUM_SPLIT = "## Tóm tắt trước đó"
REWRITE_SPLIT = "## Hội thoại gần đây"


class ConversationPromptLibrary:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._rewrite = _read(root / "rewrite.md")
        self._summary = _read(root / "summary.md")

    def rewrite_messages(self, *, history: str, question: str) -> list[LLMMessage]:
        head, separator, tail = self._rewrite.partition(REWRITE_SPLIT)
        system = head.strip()
        body = separator + tail
        # Thay khóa trực tiếp: mẫu có ví dụ JSON dùng ngoặc nhọn, không dùng str.format.
        user = body.replace("{history}", history or "(chưa có hội thoại)").replace(
            "{question}", question
        )
        return [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user.strip()),
        ]

    def summary_messages(
        self,
        *,
        previous_summary: str | None,
        messages: str,
        max_words: int,
    ) -> list[LLMMessage]:
        head, separator, tail = self._summary.partition(SUM_SPLIT)
        system = head.strip().replace("{max_words}", str(max_words))
        body = (
            (separator + tail)
            .replace("{previous_summary}", previous_summary or "(chưa có)")
            .replace("{messages}", messages)
        )
        return [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=body.strip()),
        ]


def _read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy prompt: {path}")
    return path.read_text(encoding="utf-8")
