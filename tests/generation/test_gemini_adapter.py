from __future__ import annotations

import json

import httpx
import pytest
from app.services.generation.config import PricingConfig
from app.services.generation.providers import LLMError, LLMMessage
from app.services.generation.providers.gemini import GeminiAdapter

MESSAGES = [
    LLMMessage(role="system", content="Chỉ trả JSON."),
    LLMMessage(role="user", content="Câu hỏi?"),
]

SUCCESS = {
    "candidates": [
        {
            "content": {
                "parts": [
                    {"text": "suy nghĩ nội bộ", "thought": True},
                    {"text": '{"answer": "ok"}'},
                ]
            },
            "finishReason": "STOP",
        }
    ],
    "usageMetadata": {
        "promptTokenCount": 100,
        "candidatesTokenCount": 40,
        "thoughtsTokenCount": 10,
    },
    "modelVersion": "gemini-3.8-flash",
}


def _adapter(handler, **kwargs) -> GeminiAdapter:
    transport = httpx.MockTransport(handler)
    return GeminiAdapter(
        "key-1",
        transport=transport,
        sleep=lambda _: None,
        pricing=PricingConfig(input_per_million=0.75, output_per_million=3.75),
        **kwargs,
    )


def test_payload_uses_thinking_config_and_no_temperature() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=SUCCESS)

    adapter = _adapter(handler, thinking_level="high")
    response = adapter.complete(MESSAGES)

    config = captured["generationConfig"]
    assert config["thinkingConfig"] == {"thinkingLevel": "high"}
    assert config["responseMimeType"] == "application/json"
    assert "temperature" not in config
    assert "topP" not in config
    assert "topK" not in config
    assert captured["systemInstruction"]["parts"][0]["text"] == "Chỉ trả JSON."
    assert captured["contents"][0]["role"] == "user"

    assert response.text == '{"answer": "ok"}'
    assert response.usage.input_tokens == 100
    assert response.usage.output_tokens == 50
    assert response.cost_usd == pytest.approx(100 / 1e6 * 0.75 + 50 / 1e6 * 3.75)


def test_json_mode_can_be_disabled() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=SUCCESS)

    _adapter(handler).complete(MESSAGES, json_mode=False)
    assert "responseMimeType" not in captured["generationConfig"]


def test_retries_retryable_status_with_backoff() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(503, json={"error": {"message": "high demand"}})
        return httpx.Response(200, json=SUCCESS)

    adapter = _adapter(handler, max_retries=1)
    response = adapter.complete(MESSAGES)
    assert calls["count"] == 2
    assert response.text


def test_non_retryable_status_raises_once() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    adapter = _adapter(handler, max_retries=2)
    with pytest.raises(LLMError) as info:
        adapter.complete(MESSAGES)
    assert info.value.status_code == 400
    assert not info.value.retryable
    assert calls["count"] == 1


def test_rotates_key_on_retryable_error() -> None:
    keys: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        keys.append(request.headers["x-goog-api-key"])
        if len(keys) == 1:
            return httpx.Response(429, json={"error": {"message": "rate"}})
        return httpx.Response(200, json=SUCCESS)

    adapter = _adapter(handler, max_retries=1)
    adapter._keys = ["key-a", "key-b"]
    adapter.complete(MESSAGES)
    assert keys == ["key-a", "key-b"]


def test_empty_candidate_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": []})

    with pytest.raises(LLMError, match="ứng viên"):
        _adapter(handler).complete(MESSAGES)


def test_max_tokens_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "x"}]}, "finishReason": "MAX_TOKENS"}
                ]
            },
        )

    with pytest.raises(LLMError, match="MAX_TOKENS"):
        _adapter(handler).complete(MESSAGES)


def test_missing_key_is_configuration_error() -> None:
    from app.services.generation.providers import LLMConfigurationError

    with pytest.raises(LLMConfigurationError):
        GeminiAdapter("  ")
