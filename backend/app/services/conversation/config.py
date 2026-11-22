from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "conversation.yaml"
PROMPT_ROOT = PROJECT_ROOT / "prompts" / "conversation"


@dataclass(frozen=True)
class CondensationConfig:
    enabled: bool = True
    history_turns: int = 4
    max_output_tokens: int = 256
    timeout_ms: int = 8000
    thinking_level: str = "low"
    max_rewrite_chars: int = 2000

    def __post_init__(self) -> None:
        if self.history_turns < 1:
            raise ValueError("condensation.history_turns phải >= 1")
        if self.max_output_tokens <= 0 or self.timeout_ms <= 0:
            raise ValueError("condensation.max_output_tokens/timeout_ms phải > 0")
        if self.thinking_level not in ("low", "medium", "high"):
            raise ValueError("condensation.thinking_level không hợp lệ")


@dataclass(frozen=True)
class SummaryConfig:
    enabled: bool = True
    trigger_turns: int = 10
    trigger_tokens: int = 4000
    keep_recent_turns: int = 6
    min_messages: int = 4
    max_output_tokens: int = 512
    timeout_ms: int = 20000
    thinking_level: str = "low"
    max_summary_tokens: int = 400
    workers: int = 2

    def __post_init__(self) -> None:
        if self.trigger_turns < 2:
            raise ValueError("summary.trigger_turns phải >= 2")
        if not 1 <= self.keep_recent_turns < self.trigger_turns:
            raise ValueError("summary.keep_recent_turns phải trong [1, trigger_turns)")
        if self.trigger_tokens <= 0 or self.max_summary_tokens <= 0:
            raise ValueError("summary.trigger_tokens/max_summary_tokens phải > 0")
        if self.workers < 1:
            raise ValueError("summary.workers phải >= 1")


@dataclass(frozen=True)
class ConversationContextConfig:
    max_conversation_tokens: int = 1500
    chars_per_token: float = 3.0
    max_message_chars: int = 4000

    def __post_init__(self) -> None:
        if self.max_conversation_tokens <= 0:
            raise ValueError("context.max_conversation_tokens phải > 0")
        if self.chars_per_token <= 0:
            raise ValueError("context.chars_per_token phải > 0")
        if self.max_message_chars < 200:
            raise ValueError("context.max_message_chars phải >= 200")


@dataclass(frozen=True)
class ConversationConfig:
    version: int = 1
    prompt_version: str = "v1"
    condensation: CondensationConfig = field(default_factory=CondensationConfig)
    summary: SummaryConfig = field(default_factory=SummaryConfig)
    context: ConversationContextConfig = field(default_factory=ConversationContextConfig)

    @property
    def prompt_root(self) -> Path:
        return PROMPT_ROOT / self.prompt_version

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ConversationConfig:
        def section(name: str) -> dict[str, Any]:
            value = raw.get(name) or {}
            if not isinstance(value, dict):
                raise ValueError(f"{name} phải là ánh xạ YAML")
            return value

        return cls(
            version=int(raw.get("version", 1)),
            prompt_version=str(raw.get("prompt_version", "v1")),
            condensation=CondensationConfig(**section("condensation")),
            summary=SummaryConfig(**section("summary")),
            context=ConversationContextConfig(**section("context")),
        )


def load_conversation_config(path: str | Path | None = None) -> ConversationConfig:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp cấu hình: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("Tệp cấu hình phải chứa một ánh xạ YAML")
    return ConversationConfig.from_dict(raw)
