from __future__ import annotations

import pytest
from app.services.generation.config import GenerationConfig
from app.services.generation.providers import (
    GeminiAdapter,
    LLMConfigurationError,
    OpenAICompatAdapter,
    build_provider_chain,
)

RAW = {
    "prompt_version": "v1",
    "providers": [
        {
            "name": "gemini_primary",
            "type": "gemini",
            "model": "gemini-3.8-flash",
            "api_key_env": "GEMINI_API_KEY",
        },
        {
            "name": "deepseek_fallback",
            "type": "openai_compat",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "OPENAI_API_KEY",
            "base_url_env": "OPENAI_BASE_URL",
            "model_env": "OPENAI_MODEL",
        },
    ],
    "chain": ["gemini_primary", "deepseek_fallback"],
}


def _config(**overrides) -> GenerationConfig:
    return GenerationConfig.from_dict({**RAW, **overrides})


def test_builds_gemini_when_only_gemini_key() -> None:
    chain = build_provider_chain(_config(), environ={"GEMINI_API_KEY": "g"})
    try:
        assert chain.names == ("gemini_primary",)
        assert isinstance(chain.providers[0], GeminiAdapter)
    finally:
        chain.close()


def test_builds_deepseek_when_only_openai_key() -> None:
    environ = {
        "OPENAI_API_KEY": "d",
        "OPENAI_BASE_URL": "https://api.deepseek.com/v1",
        "OPENAI_MODEL": "deepseek-chat",
    }
    chain = build_provider_chain(_config(), environ=environ)
    try:
        assert chain.names == ("deepseek_fallback",)
        adapter = chain.providers[0]
        assert isinstance(adapter, OpenAICompatAdapter)
        assert adapter.model == "deepseek-chat"
        assert adapter.endpoint.endswith("/chat/completions")
    finally:
        chain.close()


def test_env_overrides_base_url_and_model() -> None:
    environ = {
        "OPENAI_API_KEY": "d",
        "OPENAI_BASE_URL": "http://localhost:9000/v1",
        "OPENAI_MODEL": "local-model",
    }
    chain = build_provider_chain(_config(chain=["deepseek_fallback"]), environ=environ)
    try:
        adapter = chain.providers[0]
        assert adapter.base_url == "http://localhost:9000/v1"
        assert adapter.model == "local-model"
    finally:
        chain.close()


def test_disabled_provider_skipped() -> None:
    raw = {
        **RAW,
        "providers": [
            {**RAW["providers"][0], "enabled": False},
            RAW["providers"][1],
        ],
    }
    chain = build_provider_chain(
        GenerationConfig.from_dict(raw),
        environ={"GEMINI_API_KEY": "g", "OPENAI_API_KEY": "d"},
    )
    try:
        assert chain.names == ("deepseek_fallback",)
    finally:
        chain.close()


def test_no_credentials_raises() -> None:
    with pytest.raises(LLMConfigurationError, match="Không dựng được provider"):
        build_provider_chain(_config(), environ={})
