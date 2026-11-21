from __future__ import annotations

import re
import unicodedata

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_ENGLISH_TERM_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-_./][A-Za-z0-9]+)*")

VIETNAMESE_STOPWORDS = {
    "a", "ai", "bao", "bi", "boi", "cac", "cach", "can", "chi", "cho", "co", "con",
    "cua", "cung", "de", "den", "di", "do", "duoc", "gi", "hai", "hay", "hoac", "hoi",
    "khi", "khong", "la", "lai", "lam", "mot", "nao", "nay", "nen", "neu", "nhi",
    "nhieu", "nhung", "o", "phan", "phai", "sau", "se", "so", "su", "tai", "the",
    "thi", "theo", "tren", "trong", "tu", "va", "vai", "ve", "vi", "voi",
    "vua", "giua", "ra", "vao", "len", "xuong", "rat", "hon", "nhat",
}  # fmt: skip

ENGLISH_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for",
    "from", "how", "in", "is", "it", "of", "on", "or", "the", "this", "to", "what",
    "when", "which", "why", "with", "you", "your", "should", "would", "will",
}  # fmt: skip


def strip_accents(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def normalize_query(query: str) -> str:
    return " ".join(unicodedata.normalize("NFC", query).split())


def extract_lexical_terms(text: str, min_length: int, max_terms: int) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for raw in _TOKEN_RE.findall(text):
        token = raw.casefold()
        if len(token) < min_length:
            continue
        if strip_accents(token) in VIETNAMESE_STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        terms.append(token)
        if len(terms) >= max_terms:
            break
    return terms


def build_tsquery(terms: list[str]) -> str | None:
    # to_tsquery nhận lexeme; tiền tố giúp khớp dạng biến cách tiếng Việt.
    parts: list[str] = []
    for term in terms:
        cleaned = "".join(_TOKEN_RE.findall(term))
        if not cleaned:
            continue
        parts.append(f"{cleaned}:*" if len(cleaned) >= 3 else cleaned)
    return " | ".join(parts) if parts else None


def extract_english_terms(text: str, min_length: int, max_terms: int) -> list[str]:
    """Lấy thuật ngữ tiếng Anh: chữ hoa, chữ số hoặc dấu nối phân biệt với âm tiết Việt."""
    terms: list[str] = []
    seen: set[str] = set()
    for raw in _ENGLISH_TERM_RE.findall(text):
        if not (
            any(char.isupper() for char in raw)
            or any(char.isdigit() for char in raw)
            or any(separator in raw for separator in "-_./")
        ):
            continue
        term = raw.strip("-_./").casefold()
        if len(term) < min_length or term in ENGLISH_STOPWORDS:
            continue
        if term in seen:
            continue
        seen.add(term)
        terms.append(term)
        if len(terms) >= max_terms:
            break
    return terms


def word_count(text: str) -> int:
    return len(_TOKEN_RE.findall(text))
