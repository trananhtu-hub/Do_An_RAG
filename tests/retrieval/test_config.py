from __future__ import annotations

import pytest
from app.services.retrieval.config import RetrievalConfig, load_config


def test_load_repo_config_has_required_parameters() -> None:
    config = load_config()
    assert config.vector.weight == 1.0
    assert config.lexical.weight == 0.3
    assert config.fusion.k == 60
    assert config.top_k.min == 3
    assert config.top_k.max == 8
    assert config.cache.ttl_seconds == 3600
    assert config.top_k.type_ranges["nhieu_rang_buoc"] == (5, 8)


def test_defaults_apply_when_sections_missing() -> None:
    config = RetrievalConfig.from_dict({})
    assert config.fusion.k == 60
    assert config.rerank.model == "BAAI/bge-reranker-v2-m3"
    assert config.top_k.adaptive is True


def test_with_overrides_deep_merges_and_keeps_other_values() -> None:
    config = load_config().with_overrides({"rerank": {"enabled": False}, "top_k": {"default": 4}})
    assert config.rerank.enabled is False
    assert config.rerank.model == "BAAI/bge-reranker-v2-m3"
    assert config.top_k.default == 4
    assert config.top_k.min == 3


def test_fingerprint_is_stable_and_changes_with_overrides() -> None:
    config = load_config()
    assert config.fingerprint() == load_config().fingerprint()
    assert config.fingerprint() != config.with_overrides({"fusion": {"k": 10}}).fingerprint()


def test_rejects_unknown_fusion_method() -> None:
    with pytest.raises(ValueError, match="rrf"):
        RetrievalConfig.from_dict({"fusion": {"method": "bm25"}})


def test_rejects_invalid_trigram_threshold() -> None:
    with pytest.raises(ValueError, match="min_matched_terms"):
        RetrievalConfig.from_dict({"lexical": {"trigram": {"min_matched_terms": 0}}})


def test_rejects_invalid_top_k_range() -> None:
    with pytest.raises(ValueError, match="type_ranges"):
        RetrievalConfig.from_dict({"top_k": {"type_ranges": {"tra_cuu": [5, 3]}}})


def test_source_filter_is_off_by_default_and_parses_rules() -> None:
    assert RetrievalConfig.from_dict({}).rerank.source_filter.enabled is False
    config = RetrievalConfig.from_dict(
        {
            "rerank": {
                "source_filter": {
                    "enabled": True,
                    "exclude_kinds": ["question"],
                    "bypass_patterns": [r"\bcâu\s*\d+"],
                }
            }
        }
    )
    assert config.rerank.source_filter.exclude_kinds == ("question",)
    assert config.rerank.source_filter.bypass_patterns == (r"\bcâu\s*\d+",)


def test_rejects_invalid_rerank_content_scope() -> None:
    with pytest.raises(ValueError, match="content_scope"):
        RetrievalConfig.from_dict({"rerank": {"content_scope": "grandparent"}})


def test_rejects_source_filter_without_excluded_kinds() -> None:
    with pytest.raises(ValueError, match="exclude_kinds"):
        RetrievalConfig.from_dict({"rerank": {"source_filter": {"enabled": True}}})


def test_rejects_invalid_source_filter_pattern() -> None:
    with pytest.raises(ValueError, match="bypass_patterns"):
        RetrievalConfig.from_dict(
            {
                "rerank": {
                    "source_filter": {
                        "enabled": True,
                        "exclude_kinds": ["question"],
                        "bypass_patterns": ["(unclosed"],
                    }
                }
            }
        )
