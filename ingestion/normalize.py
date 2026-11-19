from __future__ import annotations

import hashlib
import re
import unicodedata

_QUOTE_TRANSLATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "–": "-",
        "—": "-",
        "−": "-",
    }
)


def normalize_text(text: str) -> str:
    """Chuẩn hóa Unicode NFC, khoảng trắng, dấu câu và ngắt dòng do PDF."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.translate(_QUOTE_TRANSLATION)
    text = text.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    text = text.replace("​", "").replace("﻿", "")
    text = text.replace("­", "").replace("…", "...")
    text = re.sub(r"(?<=[^\W\d_])-\n(?=[^\W\d_])", "", text)
    text = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n"))
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def flatten_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_fragment(text: str) -> str:
    text = flatten_text(text)
    text = text.strip(" \t\n:;,-")
    text = text.strip("\"'")
    text = re.sub(r"^(?:rằng|ghi rằng)\s*:?\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
