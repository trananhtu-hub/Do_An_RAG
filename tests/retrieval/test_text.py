from __future__ import annotations

from app.services.retrieval.text import (
    build_tsquery,
    extract_english_terms,
    extract_lexical_terms,
    normalize_query,
    strip_accents,
    word_count,
)


def test_strip_accents_handles_vietnamese_d() -> None:
    assert strip_accents("Đồ Án RAG") == "Do An RAG"


def test_normalize_query_collapses_whitespace() -> None:
    assert normalize_query("  So   sánh\tS3  ") == "So sánh S3"


def test_extract_lexical_terms_drops_stopwords_and_short_tokens() -> None:
    terms = extract_lexical_terms("Sự khác nhau giữa S3 và EC2 là gì", 2, 24)
    assert "s3" in terms
    assert "ec2" in terms
    assert "la" not in terms
    assert "gi" not in terms


def test_build_tsquery_uses_prefix_for_long_terms() -> None:
    query = build_tsquery(["s3", "glacier", "dữ"])
    assert query == "s3 | glacier:* | dữ"


def test_build_tsquery_returns_none_without_terms() -> None:
    assert build_tsquery([]) is None


def test_extract_english_terms_ignores_unaccented_vietnamese_words() -> None:
    terms = extract_english_terms(
        "Sự khác nhau giữa S3 Glacier Deep Archive và Standard khi truy xuất dữ liệu", 2, 8
    )
    assert terms == ["s3", "glacier", "deep", "archive", "standard"]


def test_extract_english_terms_keeps_hyphenated_service_names() -> None:
    terms = extract_english_terms("So sánh Multi-AZ và Read Replica cho RDS", 2, 8)
    assert "multi-az" in terms
    assert "rds" in terms


def test_extract_english_terms_drops_english_stopwords() -> None:
    assert extract_english_terms("The Service is AWS", 2, 8) == ["service", "aws"]


def test_word_count_uses_alphanumeric_tokens() -> None:
    assert word_count("S3 có 3 lớp lưu trữ") == 6
