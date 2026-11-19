from __future__ import annotations

from math import ceil

from .config import CHARS_PER_TOKEN


def estimate_tokens(text: str) -> int:
    if not text or not text.strip():
        return 0
    return max(1, ceil(len(text) / CHARS_PER_TOKEN))
