from __future__ import annotations

import json

import httpx
import pytest
from app.services.generation.providers import LLMError, LLMMessage
from app.services.generation.providers.openai_compat import OpenAICompatAdapter

MESSAGES = [
    LLMMessage(role="system", content="Chỉ trả JSON."),
    LLMMessage(role="user", content="Câu hỏi?"),
]

SUCCESS = {
    "id": "chatcmpl-1",
    "model": "deepseek-chat",
    "choices": [
        {"message": {"role": "assistant", "content": '{"answer": "ok"}'}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 80, "completion_tokens": 20},
}


def _adapter(handler, **kwargs) -> OpenAICompatAdapter:
    return OpenAICompatAdapter(
        "https://api.deepseek.com/v1",
        api_key="secret",
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
        **kwargs,
    )


def test_posts_to_chat_completions_with_bearer() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=SUCCESS)

    response = _adapter(handler, model="deepseek-chat").complete(MESSAGES)
    assert captured["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert captured["auth"] == "Bearer secret"
    assert captured["body"]["model"] == "deepseek-chat"
    assert captured["body"]["messages"][0] == {"role": "system", "content": "Chỉ trả JSON."}
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert "temperature" not in captured["body"]
    assert response.text == '{"answer": "ok"}'
    assert response.usage.input_tokens == 80
    assert response.usage.output_tokens == 20


def test_temperature_included_when_configured() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=SUCCESS)

    _adapter(handler, model="deepseek-chat", temperature=0.1).complete(MESSAGES)
    assert captured["temperature"] == 0.1


def test_retries_without_response_format_on_400() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if "response_format" in body:
            return httpx.Response(
                400, json={"error": {"message": "response_format is not supported"}}
            )
        return httpx.Response(200, json=SUCCESS)

    response = _adapter(handler, model="deepseek-chat").complete(MESSAGES)
    assert len(bodies) == 2
    assert "response_format" not in bodies[1]
    assert response.text


def test_retryable_status_retried() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(502, text="bad gateway")
        return httpx.Response(200, json=SUCCESS)

    _adapter(handler, model="deepseek-chat", max_retries=1).complete(MESSAGES)
    assert calls["count"] == 2


def test_missing_choices_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    with pytest.raises(LLMError, match="choices"):
        _adapter(handler, model="deepseek-chat").complete(MESSAGES)


def test_empty_content_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]}
        )

    with pytest.raises(LLMError, match="rỗng"):
        _adapter(handler, model="deepseek-chat").complete(MESSAGES)


def test_empty_content_is_retried() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": ""}, "finish_reason": "length"}]},
            )
        return httpx.Response(200, json=SUCCESS)

    response = _adapter(handler, model="deepseek-chat", max_retries=1).complete(MESSAGES)
    assert response.text
    assert calls["count"] == 2


def test_list_content_parts_supported() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": [{"type": "text", "text": '{"a":1}'}],
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    assert _adapter(handler, model="x").complete(MESSAGES).text == '{"a":1}'


def test_endpoint_with_full_path_kept() -> None:
    adapter = OpenAICompatAdapter(
        "http://localhost:9/v1/chat/completions",
        model="x",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=SUCCESS)),
    )
    assert adapter.endpoint == "http://localhost:9/v1/chat/completions"


def test_missing_base_url_rejected() -> None:
    with pytest.raises(LLMError):
        OpenAICompatAdapter("", model="x")
