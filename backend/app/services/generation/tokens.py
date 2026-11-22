"""Đếm token prompt bằng tokenizer DeepSeek và kiểm kê theo thành phần.

Tokenizer lấy từ tệp ``tokenizer.json`` (biến môi trường ``DEEPSEEK_TOKENIZER_PATH``
hoặc bộ nhớ đệm Hugging Face của ``deepseek-ai/DeepSeek-V3``). Khi không có tệp,
lớp đếm lùi về ước lượng ký tự/token và đánh dấu ``exact = False``.
"""

from __future__ import annotations

import math
import os
import re
import threading
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from .providers import LLMMessage

_TOKENIZER_REPO = "deepseek-ai/DeepSeek-V3"
_TOKENIZER_FILE = "tokenizer.json"

_SECTION_PATTERN = re.compile(r"(?m)^# (NGỮ CẢNH HỘI THOẠI|NGỮ CẢNH|CÂU HỎI|YÊU CẦU ĐẦU RA)\s*$")
_FEW_SHOT_PATTERN = re.compile(r"(?m)^#{1,3} Ví dụ[^\n]*$")
_FILE_SEPARATOR = "\n\n---\n\n"


class PromptTokenCounter:
    def __init__(
        self,
        *,
        chars_per_token: float = 3.5,
        tokenizer_path: str | Path | None = None,
    ) -> None:
        self.chars_per_token = max(0.1, chars_per_token)
        self.source = "estimate_chars"
        self.exact = False
        self._tokenizer = None
        path = _resolve_tokenizer_path(tokenizer_path)
        if path is not None:
            try:
                from tokenizers import Tokenizer

                self._tokenizer = Tokenizer.from_file(str(path))
                self.exact = True
                self.source = str(path)
            except Exception:  # noqa: BLE001 - thiếu tokenizer thì lùi về ước lượng
                self._tokenizer = None

    def count(self, text: str) -> int:
        if not text:
            return 0
        if self._tokenizer is not None:
            return len(self._tokenizer.encode(text, add_special_tokens=False).ids)
        return math.ceil(len(text) / self.chars_per_token)


_default_counter: PromptTokenCounter | None = None
_default_lock = threading.Lock()


def default_token_counter() -> PromptTokenCounter:
    """Bộ đếm dùng chung, nạp tokenizer một lần cho cả tiến trình."""
    global _default_counter
    if _default_counter is None:
        with _default_lock:
            if _default_counter is None:
                _default_counter = PromptTokenCounter()
    return _default_counter


@dataclass(frozen=True)
class PromptAudit:
    system_tokens: int
    few_shot_tokens: int
    context_tokens: int
    conversation_tokens: int
    question_tokens: int
    instruction_tokens: int
    overhead_tokens: int
    total_tokens: int
    limit_tokens: int
    exact: bool
    over_limit: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_prompt(
    messages: Sequence[LLMMessage],
    counter: PromptTokenCounter,
    *,
    limit_tokens: int = 0,
) -> PromptAudit:
    """Kiểm kê token của prompt đã dựng; tổng tính trên toàn văn, không cộng dồn phần."""
    system = "\n\n".join(message.content for message in messages if message.role == "system")
    user = "\n\n".join(message.content for message in messages if message.role != "system")
    system_total = counter.count(system)
    few_shot = counter.count(_few_shot_text(system))
    sections = _split_sections(user)
    overhead = 4 * len(messages) + 8
    total = counter.count(system) + counter.count(user) + overhead
    return PromptAudit(
        system_tokens=max(0, system_total - few_shot),
        few_shot_tokens=few_shot,
        context_tokens=counter.count(sections.get("NGỮ CẢNH", "")),
        conversation_tokens=counter.count(sections.get("NGỮ CẢNH HỘI THOẠI", "")),
        question_tokens=counter.count(sections.get("CÂU HỎI", "")),
        instruction_tokens=counter.count(sections.get("YÊU CẦU ĐẦU RA", "")),
        overhead_tokens=overhead,
        total_tokens=total,
        limit_tokens=limit_tokens,
        exact=counter.exact,
        over_limit=bool(limit_tokens) and total > limit_tokens,
    )


def _resolve_tokenizer_path(explicit: str | Path | None) -> Path | None:
    if explicit:
        path = Path(explicit)
        return path if path.exists() else None
    env_path = os.environ.get("DEEPSEEK_TOKENIZER_PATH", "").strip()
    if env_path:
        path = Path(env_path)
        return path if path.exists() else None
    try:
        from huggingface_hub import try_to_load_from_cache

        cached = try_to_load_from_cache(_TOKENIZER_REPO, _TOKENIZER_FILE)
    except Exception:  # noqa: BLE001 - không có thư viện/bộ nhớ đệm
        return None
    return Path(cached) if isinstance(cached, str) and Path(cached).exists() else None


def _split_sections(text: str) -> dict[str, str]:
    matches = list(_SECTION_PATTERN.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[match.end() : end].strip()
    return sections


def _few_shot_text(system: str) -> str:
    blocks: list[str] = []
    for match in _FEW_SHOT_PATTERN.finditer(system):
        end = system.find(_FILE_SEPARATOR, match.end())
        if end == -1:
            end = len(system)
        blocks.append(system[match.start() : end])
    return "\n\n".join(blocks)
