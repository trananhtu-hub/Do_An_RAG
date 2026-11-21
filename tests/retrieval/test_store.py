from __future__ import annotations

import pytest
from app.services.retrieval.store import PgChunkStore, _like_pattern, _trigram_query, vector_literal


def test_vector_literal_formats_postgres_vector() -> None:
    assert vector_literal([0.5, -1.0, 0.25]) == "[0.5,-1,0.25]"


def test_like_pattern_escapes_wildcards() -> None:
    assert _like_pattern("foo_bar%") == "%foo\\_bar\\%%"


def test_trigram_query_builds_one_condition_per_term() -> None:
    sql = _trigram_query(3)
    assert sql.count("c.search_text ilike %s") == 6
    assert sql.count("case when c.search_text ilike %s then 1 else 0 end") == 3
    assert "content_type = 'child'" in sql


def test_store_requires_database_url() -> None:
    with pytest.raises(ValueError, match="DATABASE_URL"):
        PgChunkStore("")


def test_store_rejects_invalid_ef_search() -> None:
    with pytest.raises(ValueError, match="ef_search"):
        PgChunkStore("postgresql://user:pass@localhost/db", ef_search=0)
