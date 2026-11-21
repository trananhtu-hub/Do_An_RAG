from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "generation.yaml"
PROMPT_ROOT = PROJECT_ROOT / "prompts"
THINKING_LEVELS = ("low", "medium", "high")
PROVIDER_TYPES = ("gemini", "openai_compat")


@dataclass(frozen=True)
class PricingConfig:
    """Giá theo USD cho 1 triệu token, dùng để ước tính chi phí mỗi câu."""

    input_per_million: float = 0.0
    output_per_million: float = 0.0

    def cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        return round(
            input_tokens / 1_000_000 * self.input_per_million
            + output_tokens / 1_000_000 * self.output_per_million,
            8,
        )


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    type: str
    model: str = ""
    enabled: bool = True
    api_key_env: str = ""
    base_url: str = ""
    base_url_env: str = ""
    model_env: str = ""
    thinking_level: str = "medium"
    timeout_ms: int = 120_000
    max_retries: int = 1
    backoff_base_s: float = 2.0
    backoff_max_s: float = 20.0
    max_output_tokens: int = 8192
    json_mode: bool = True
    temperature: float | None = None
    headers: dict[str, str] = field(default_factory=dict)
    pricing: PricingConfig = field(default_factory=PricingConfig)


@dataclass(frozen=True)
class LoggingConfig:
    enabled: bool = True
    table: str = "query_logs"


@dataclass(frozen=True)
class GenerationConfig:
    version: int = 1
    prompt_version: str = "v1"
    default_thinking_level: str = "medium"
    max_output_tokens: int = 8192
    schema_retries: int = 1
    require_citation: bool = True
    confidence_warning_threshold: float = 0.55
    max_context_tokens: int = 8000
    chars_per_token: float = 3.5
    providers: tuple[ProviderConfig, ...] = ()
    chain: tuple[str, ...] = ()
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def __post_init__(self) -> None:
        if self.default_thinking_level not in THINKING_LEVELS:
            raise ValueError(
                f"default_thinking_level phải thuộc {THINKING_LEVELS}, "
                f"nhận {self.default_thinking_level!r}"
            )
        if not 0 <= self.schema_retries <= 2:
            raise ValueError("schema_retries phải trong [0, 2]")
        if not 0.0 <= self.confidence_warning_threshold <= 1.0:
            raise ValueError("confidence_warning_threshold phải trong [0, 1]")
        if self.max_context_tokens <= 0 or self.max_output_tokens <= 0:
            raise ValueError("max_context_tokens và max_output_tokens phải lớn hơn 0")
        if self.chars_per_token <= 0:
            raise ValueError("chars_per_token phải lớn hơn 0")
        names = {provider.name for provider in self.providers}
        if len(names) != len(self.providers):
            raise ValueError("Tên provider phải duy nhất")
        for name in self.chain:
            if name not in names:
                raise ValueError(f"Provider trong chain không tồn tại: {name}")
        for provider in self.providers:
            if provider.type not in PROVIDER_TYPES:
                raise ValueError(f"Loại provider không hợp lệ: {provider.type}")
            if provider.thinking_level not in THINKING_LEVELS:
                raise ValueError(f"thinking_level của {provider.name} phải thuộc {THINKING_LEVELS}")
            if provider.timeout_ms <= 0 or provider.max_retries < 0:
                raise ValueError(f"timeout_ms/max_retries của {provider.name} không hợp lệ")
            if provider.temperature is not None and provider.type == "gemini":
                raise ValueError(
                    "Gemini 3.8 Flash không nhận temperature; điều khiển bằng thinking_level"
                )

    @property
    def provider_map(self) -> dict[str, ProviderConfig]:
        return {provider.name: provider for provider in self.providers}

    @property
    def prompt_root(self) -> Path:
        return PROMPT_ROOT / self.prompt_version

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> GenerationConfig:
        providers_raw = raw.get("providers") or []
        if not isinstance(providers_raw, list | tuple):
            raise ValueError("providers phải là danh sách")
        providers = tuple(_provider_from_dict(item) for item in providers_raw)
        chain = raw.get("chain")
        if chain is None:
            chain = tuple(provider.name for provider in providers if provider.enabled)
        if not isinstance(chain, list | tuple):
            raise ValueError("chain phải là danh sách tên provider")
        logging_raw = raw.get("logging") or {}
        return cls(
            version=int(raw.get("version", 1)),
            prompt_version=str(raw.get("prompt_version", "v1")),
            default_thinking_level=str(raw.get("default_thinking_level", "medium")),
            max_output_tokens=int(raw.get("max_output_tokens", 8192)),
            schema_retries=int(raw.get("schema_retries", 1)),
            require_citation=bool(raw.get("require_citation", True)),
            confidence_warning_threshold=float(raw.get("confidence_warning_threshold", 0.55)),
            max_context_tokens=int(raw.get("max_context_tokens", 8000)),
            chars_per_token=float(raw.get("chars_per_token", 3.5)),
            providers=providers,
            chain=tuple(str(name) for name in chain),
            logging=LoggingConfig(
                enabled=bool(logging_raw.get("enabled", True)),
                table=str(logging_raw.get("table", "query_logs")),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def fingerprint(self) -> str:
        data = self.to_dict()
        payload = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def with_overrides(self, overrides: dict[str, Any]) -> GenerationConfig:
        return GenerationConfig.from_dict(_deep_merge(self.to_dict(), overrides))


def _provider_from_dict(raw: Any) -> ProviderConfig:
    if not isinstance(raw, dict):
        raise ValueError("Mỗi provider phải là ánh xạ")
    name = str(raw.get("name") or "").strip()
    if not name:
        raise ValueError("Provider thiếu tên")
    pricing_raw = raw.get("pricing") or {}
    headers = raw.get("headers") or {}
    if not isinstance(headers, dict):
        raise ValueError(f"headers của {name} phải là ánh xạ")
    return ProviderConfig(
        name=name,
        type=str(raw.get("type") or ""),
        model=str(raw.get("model") or ""),
        enabled=bool(raw.get("enabled", True)),
        api_key_env=str(raw.get("api_key_env") or ""),
        base_url=str(raw.get("base_url") or ""),
        base_url_env=str(raw.get("base_url_env") or ""),
        model_env=str(raw.get("model_env") or ""),
        thinking_level=str(raw.get("thinking_level", "medium")),
        timeout_ms=int(raw.get("timeout_ms", 120_000)),
        max_retries=int(raw.get("max_retries", 1)),
        backoff_base_s=float(raw.get("backoff_base_s", 2.0)),
        backoff_max_s=float(raw.get("backoff_max_s", 20.0)),
        max_output_tokens=int(raw.get("max_output_tokens", 8192)),
        json_mode=bool(raw.get("json_mode", True)),
        temperature=(None if raw.get("temperature") is None else float(raw["temperature"])),
        headers={str(key): str(value) for key, value in headers.items()},
        pricing=PricingConfig(
            input_per_million=float(pricing_raw.get("input_per_million", 0.0)),
            output_per_million=float(pricing_raw.get("output_per_million", 0.0)),
        ),
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_generation_config(path: str | Path | None = None) -> GenerationConfig:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp cấu hình: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("Tệp cấu hình phải chứa một ánh xạ YAML")
    return GenerationConfig.from_dict(raw)
