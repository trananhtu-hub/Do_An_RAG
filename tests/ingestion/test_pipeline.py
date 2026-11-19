from __future__ import annotations

import json

import pytest

from ingestion.config import PIPELINE_VERSION, Settings
from ingestion.pipeline import (
    _domain_shares,
    _input_paths,
    _is_current,
    _load_embed_cache,
    _safe_error,
    _save_embed_cache,
    _write_stats,
)
from ingestion.store import StoredDocument


def _stored(**overrides) -> StoredDocument:
    metadata = {
        "pipeline_version": PIPELINE_VERSION,
        "question_count": 2,
        "document_title": "Tài liệu thử",
        "page_count": 1,
        "empty_pages": [],
        "table_count": 0,
    }
    metadata.update(overrides.pop("metadata", {}))
    values = {
        "id": "00000000-0000-0000-0000-000000000001",
        "source_key": "data/raw/test.pdf",
        "checksum": "abc",
        "page_count": 1,
        "metadata": metadata,
        "chunk_count": 4,
        "parent_count": 1,
        "child_count": 3,
        "null_embeddings": 0,
        "question_count": 2,
    }
    values.update(overrides)
    return StoredDocument(**values)


def test_is_current_chi_bo_qua_khi_day_du_dieu_kien():
    assert _is_current(_stored(), "abc", force=False) is True
    assert _is_current(_stored(), "khac", force=False) is False
    assert _is_current(_stored(), "abc", force=True) is False
    assert _is_current(None, "abc", force=False) is False
    assert _is_current(_stored(null_embeddings=1), "abc", force=False) is False
    assert _is_current(_stored(chunk_count=0), "abc", force=False) is False
    assert _is_current(_stored(question_count=1), "abc", force=False) is False
    assert _is_current(_stored(metadata={"pipeline_version": "0.9.0"}), "abc", force=False) is False


def test_input_paths_tu_choi_external_test(tmp_path):
    external = tmp_path / "data" / "external_test" / "de-thi.pdf"
    external.parent.mkdir(parents=True)
    external.write_bytes(b"%PDF-1.4")
    with pytest.raises(RuntimeError, match="external_test"):
        _input_paths(external)


def test_input_paths_tu_choi_tep_khong_phai_pdf(tmp_path):
    path = tmp_path / "ghi-chu.txt"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="không phải PDF"):
        _input_paths(path)


def test_input_paths_nhan_thu_muc_va_tep_pdf(tmp_path):
    pdf = tmp_path / "tai-lieu.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert _input_paths(pdf) == [pdf]
    assert _input_paths(tmp_path) == [pdf]


def test_domain_shares_tinh_phan_tram():
    shares = _domain_shares(
        {
            "Secure": 30,
            "Resilient": 26,
            "High-Performing": 24,
            "Cost-Optimized": 20,
        }
    )
    assert shares == {
        "Cost-Optimized": 20.0,
        "High-Performing": 24.0,
        "Resilient": 26.0,
        "Secure": 30.0,
    }
    assert _domain_shares({}) == {}


def test_safe_error_che_khoa_va_chuoi_ket_noi():
    settings = Settings(
        gemini_api_key="khoa-bi-mat",
        database_url="postgresql://user:mat-khau@host/db",
    )
    error = RuntimeError("không kết nối được postgresql://user:mat-khau@host/db với khoa-bi-mat")
    message = _safe_error(error, settings)
    assert "mat-khau" not in message
    assert "khoa-bi-mat" not in message
    assert "***" in message


def test_gemini_api_keys_tach_theo_dau_phay():
    settings = Settings(gemini_api_key=" k1 , k2,,k1 ", database_url="postgresql://x/y")
    assert settings.gemini_api_keys == ("k1", "k2")


def test_bo_dem_embedding_luu_va_doc(tmp_path):
    path = tmp_path / "cache" / "embed_cache.json"
    _save_embed_cache(path, {"gemini-embedding-001:768:abc": [0.1, 0.2]})
    assert _load_embed_cache(path) == {"gemini-embedding-001:768:abc": [0.1, 0.2]}
    assert not path.with_suffix(".tmp").exists()
    path.write_text("hỏng", encoding="utf-8")
    assert _load_embed_cache(path) == {}
    assert _load_embed_cache(tmp_path / "khong-co.json") == {}


def test_write_stats_tao_thu_muc_va_json_utf8(tmp_path):
    path = tmp_path / "nested" / "stats.json"
    _write_stats(path, {"tài liệu": 7, "ghi_chú": "tiếng Việt"})
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["tài liệu"] == 7
    assert data["ghi_chú"] == "tiếng Việt"
    assert path.read_text(encoding="utf-8").endswith("\n")
