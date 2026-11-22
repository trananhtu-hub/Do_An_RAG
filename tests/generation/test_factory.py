from __future__ import annotations

import pytest
from app.services.generation.config import GenerationConfig
from app.services.generation.providers import (
    LLMConfigurationError,
    OpenAICompatAdapter,
    build_provider_chain,
)

RAW = {
    "prompt_version": "v1",
    "providers": [
        {
            "name": "deepseek_primary",
            "type": "openai_compat",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "DEEPSEEK_API_KEY",
            "base_url_env": "DEEPSEEK_BASE_URL",
            "model_env": "DEEPSEEK_MODEL",
        }
    ],
    "chain": ["deepseek_primary"],
}


def _config(**overrides) -> GenerationConfig:
    return GenerationConfig.from_dict({**RAW, **overrides})


def test_builds_deepseek_as_only_provider() -> None:
    environ = {
        "DEEPSEEK_API_KEY": "d",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
        "DEEPSEEK_MODEL": "deepseek-chat",
    }
    chain = build_provider_chain(_config(), environ=environ)
    try:
        assert chain.names == ("deepseek_primary",)
        adapter = chain.providers[0]
        assert isinstance(adapter, OpenAICompatAdapter)
        assert adapter.model == "deepseek-chat"
        assert adapter.endpoint == "https://api.deepseek.com/v1/chat/completions"
    finally:
        chain.close()


def test_gemini_generation_provider_is_rejected() -> None:
    raw = {
        **RAW,
        "providers": [
            {
                "name": "gemini_primary",
                "type": "gemini",
                "model": "gemini-3.8-flash",
                "api_key_env": "GEMINI_API_KEY",
            }
        ],
        "chain": ["gemini_primary"],
    }
    with pytest.raises(ValueError, match="Loại provider không hợp lệ"):
        GenerationConfig.from_dict(raw)


def test_gemini_key_cannot_build_generation_chain() -> None:
    with pytest.raises(LLMConfigurationError, match="Không dựng được provider"):
        build_provider_chain(_config(), environ={"GEMINI_API_KEY": "g"})


def test_env_overrides_base_url_and_model() -> None:
    environ = {
        "DEEPSEEK_API_KEY": "d",
        "DEEPSEEK_BASE_URL": "http://localhost:9000/v1",
        "DEEPSEEK_MODEL": "local-model",
    }
    chain = build_provider_chain(_config(), environ=environ)
    try:
        adapter = chain.providers[0]
        assert adapter.base_url == "http://localhost:9000/v1"
        assert adapter.model == "local-model"
    finally:
        chain.close()


def test_disabled_provider_skipped() -> None:
    raw = {
        **RAW,
        "providers": [{**RAW["providers"][0], "enabled": False}],
    }
    with pytest.raises(LLMConfigurationError, match="Không dựng được provider"):
        build_provider_chain(GenerationConfig.from_dict(raw), environ={"DEEPSEEK_API_KEY": "d"})


def test_no_credentials_raises() -> None:
    with pytest.raises(LLMConfigurationError, match="Không dựng được provider"):
        build_provider_chain(_config(), environ={})
