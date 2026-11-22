from __future__ import annotations

import json
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


class DeepSeekTextClient:
    """Gọi DeepSeek cho phân loại/tách truy vấn; lỗi đẩy lên cho caller dùng heuristic."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        keys = [part.strip() for part in str(api_key).split(",") if part.strip()]
        if not keys:
            raise ValueError("Thiếu DEEPSEEK_API_KEY để gọi LLM")
        self._keys = keys
        self._key_index = 0
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(transport=transport)

    def close(self) -> None:
        self._client.close()

    def generate_json(self, model: str, prompt: str, timeout_ms: int) -> dict[str, Any] | None:
        payload = {
            "model": model or DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": "Chỉ trả JSON đúng dạng yêu cầu."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 256,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        response = self._client.post(
            f"{self._base_url}/chat/completions",
            headers={
                "authorization": f"Bearer {self._keys[self._key_index % len(self._keys)]}",
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
            text = data["choices"][0]["message"]["content"]
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
