from __future__ import annotations

import os
from collections.abc import Mapping

from ..config import GenerationConfig, ProviderConfig
from .base import LLMConfigurationError, LLMProvider
from .fallback import FallbackChain
from .openai_compat import OpenAICompatAdapter


def build_provider_chain(
    config: GenerationConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> FallbackChain:
    """Dựng FallbackChain từ cấu hình, bỏ qua provider thiếu thông tin xác thực."""
    env = os.environ if environ is None else environ
    providers: list[LLMProvider] = []
    skipped: list[str] = []
    for name in config.chain:
        provider_config = config.provider_map[name]
        if not provider_config.enabled:
            skipped.append(f"{name} (tắt trong cấu hình)")
            continue
        adapter = _build_adapter(provider_config, env)
        if adapter is None:
            skipped.append(f"{name} (thiếu biến môi trường)")
            continue
        providers.append(adapter)
    if not providers:
        detail = "; ".join(skipped) if skipped else "chain rỗng"
        raise LLMConfigurationError(f"Không dựng được provider nào: {detail}")
    return FallbackChain(providers)


def _build_adapter(config: ProviderConfig, env: Mapping[str, str]) -> LLMProvider | None:
    api_key = _resolve_key(config.api_key_env, env)
    if config.api_key_env and not api_key:
        return None
    if config.type == "openai_compat":
        base_url = _resolve(config.base_url_env, env) or config.base_url
        model = _resolve(config.model_env, env) or config.model
        if not base_url or not model:
            return None
        return OpenAICompatAdapter(
            base_url,
            name=config.name,
            model=model,
            api_key=api_key,
            timeout_ms=config.timeout_ms,
            max_retries=config.max_retries,
            backoff_base_s=config.backoff_base_s,
            backoff_max_s=config.backoff_max_s,
            max_output_tokens=config.max_output_tokens,
            temperature=config.temperature,
            headers=config.headers,
            pricing=config.pricing,
        )
    raise LLMConfigurationError(f"Loại provider chưa hỗ trợ: {config.type}")


def _resolve(variable: str, env: Mapping[str, str]) -> str:
    if not variable:
        return ""
    return str(env.get(variable, "")).strip()


def _resolve_key(variable: str, env: Mapping[str, str]) -> str:
    if not variable:
        return ""
    return str(env.get(variable, "")).strip()
