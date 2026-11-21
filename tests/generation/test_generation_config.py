from __future__ import annotations

import pytest
from app.services.generation.config import (
    GenerationConfig,
    PricingConfig,
    load_generation_config,
)

RAW = {
    "version": 1,
    "prompt_version": "v1",
    "default_thinking_level": "medium",
    "providers": [
        {
            "name": "gemini_primary",
            "type": "gemini",
            "model": "gemini-3.8-flash",
            "api_key_env": "GEMINI_API_KEY",
            "thinking_level": "medium",
            "pricing": {"input_per_million": 0.75, "output_per_million": 3.75},
        },
        {
            "name": "deepseek_fallback",
            "type": "openai_compat",
            "enabled": False,
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key_env": "OPENAI_API_KEY",
        },
    ],
    "chain": ["gemini_primary", "deepseek_fallback"],
}


def test_loads_shipped_config() -> None:
    config = load_generation_config()
    assert config.prompt_version == "v1"
    assert config.chain == ("gemini_primary", "deepseek_fallback")
    assert config.provider_map["gemini_primary"].model == "gemini-3.8-flash"
    assert config.default_thinking_level == "medium"
    assert config.max_context_tokens == 8000


def test_gemini_rejects_temperature() -> None:
    raw = {
        **RAW,
        "providers": [
            {
                "name": "gemini_primary",
                "type": "gemini",
                "model": "gemini-3.8-flash",
                "temperature": 0.2,
            }
        ],
        "chain": ["gemini_primary"],
    }
    with pytest.raises(ValueError, match="temperature"):
        GenerationConfig.from_dict(raw)


def test_invalid_thinking_level() -> None:
    raw = {**RAW, "default_thinking_level": "max"}
    with pytest.raises(ValueError, match="default_thinking_level"):
        GenerationConfig.from_dict(raw)


def test_chain_must_reference_provider() -> None:
    raw = {**RAW, "chain": ["khong_ton_tai"]}
    with pytest.raises(ValueError, match="không tồn tại"):
        GenerationConfig.from_dict(raw)


def test_duplicate_provider_names_rejected() -> None:
    provider = {"name": "dup", "type": "gemini", "model": "x"}
    raw = {**RAW, "providers": [provider, provider], "chain": ["dup"]}
    with pytest.raises(ValueError, match="duy nhất"):
        GenerationConfig.from_dict(raw)


def test_pricing_cost() -> None:
    pricing = PricingConfig(input_per_million=0.75, output_per_million=3.75)
    assert pricing.cost_usd(1_000_000, 0) == 0.75
    assert pricing.cost_usd(0, 1_000_000) == 3.75
    assert pricing.cost_usd(0, 0) == 0.0


def test_with_overrides_keeps_providers() -> None:
    config = GenerationConfig.from_dict(RAW)
    overridden = config.with_overrides({"default_thinking_level": "high"})
    assert overridden.default_thinking_level == "high"
    assert overridden.chain == config.chain
    assert overridden.provider_map.keys() == config.provider_map.keys()
    assert overridden.fingerprint() != config.fingerprint()
