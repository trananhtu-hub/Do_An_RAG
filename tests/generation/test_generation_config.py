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
            "name": "deepseek_primary",
            "type": "openai_compat",
            "model": "deepseek-chat",
            "api_key_env": "DEEPSEEK_API_KEY",
        }
    ],
    "chain": ["deepseek_primary"],
}


def test_loads_shipped_config() -> None:
    config = load_generation_config()
    assert config.prompt_version == "v1"
    assert config.chain == ("deepseek_primary",)
    assert config.provider_map["deepseek_primary"].model == "deepseek-chat"
    assert config.judge_provider == "deepseek_primary"
    assert config.default_thinking_level == "medium"
    assert config.max_context_tokens == 6000
    assert config.max_output_tokens == 6144
    assert config.max_prompt_tokens == 12000


def test_simple_query_thinking_level_hop_le_voi_none() -> None:
    config = GenerationConfig.from_dict({**RAW, "simple_query_thinking_level": "none"})
    assert config.simple_query_thinking_level == "none"


def test_simple_query_thinking_level_sai_bi_tu_choi() -> None:
    with pytest.raises(ValueError, match="simple_query_thinking_level"):
        GenerationConfig.from_dict({**RAW, "simple_query_thinking_level": "siêu nhanh"})


def test_shipped_config_has_no_gemini_generation_path() -> None:
    config = load_generation_config()
    assert all(provider.type == "openai_compat" for provider in config.providers)
    assert all("gemini" not in provider.name for provider in config.providers)


def test_gemini_provider_type_rejected() -> None:
    raw = {
        **RAW,
        "providers": [
            {
                "name": "gemini_primary",
                "type": "gemini",
                "model": "gemini-3.8-flash",
            }
        ],
        "chain": ["gemini_primary"],
    }
    with pytest.raises(ValueError, match="Loại provider không hợp lệ"):
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
    provider = {"name": "dup", "type": "openai_compat", "model": "x"}
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
