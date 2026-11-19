from __future__ import annotations

from ingestion.normalize import flatten_text, normalize_text, sha256_text


def test_normalize_unicode_nfc_va_khoang_trang():
    decomposed = "Câu hỏi    số 1"
    result = normalize_text(decomposed)
    assert result == "Câu hỏi số 1"


def test_flatten_text_gop_dong_va_chuan_hoa_dau_cau():
    result = flatten_text(normalize_text("Dòng một , dòng hai.\nDòng ba ;  dòng bốn"))
    assert result == "Dòng một, dòng hai. Dòng ba; dòng bốn"


def test_sha256_on_dinh():
    assert sha256_text("nội dung") == sha256_text("nội dung")
    assert sha256_text("nội dung") != sha256_text("nội dung khác")
    assert len(sha256_text("x")) == 64
