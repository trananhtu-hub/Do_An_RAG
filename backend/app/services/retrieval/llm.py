from __future__ import annotations

import json
from typing import Any

import httpx

GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiTextClient:
    """Gọi Gemini để phân loại/tách truy vấn; lỗi được đẩy lên cho caller fallback."""

    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        keys = [part.strip() for part in str(api_key).split(",") if part.strip()]
        if not keys:
            raise ValueError("Thiếu GEMINI_API_KEY để gọi LLM")
        self._keys = keys
        self._key_index = 0
        self._client = httpx.Client(transport=transport)

    def close(self) -> None:
        self._client.close()

    def generate_json(self, model: str, prompt: str, timeout_ms: int) -> dict[str, Any] | None:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 256,
                "responseMimeType": "application/json",
            },
        }
        response = self._client.post(
            GENERATE_URL.format(model=model),
            headers={
                "x-goog-api-key": self._keys[self._key_index % len(self._keys)],
                "content-type": "application/json",
            },
            json=payload,
            timeout=timeout_ms / 1000.0,
        )
        if response.status_code in {429, 500, 502, 503, 504}:
            self._key_index += 1
        if response.status_code >= 400:
            return None
        try:
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (ValueError, KeyError, IndexError, TypeError):
            return None
        return _parse_json_object(text)


def _parse_json_object(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
