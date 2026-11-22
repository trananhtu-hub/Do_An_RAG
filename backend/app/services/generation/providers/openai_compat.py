from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator, Sequence

import httpx

from ..config import PricingConfig
from .base import (
    LLMError,
    LLMMessage,
    LLMResponse,
    StreamDelta,
    Usage,
    estimate_usage,
    retry_call,
)

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class OpenAICompatAdapter:
    """Adapter cho mọi endpoint tương thích OpenAI Chat Completions.

    base_url là gốc API đã gồm phần phiên bản (ví dụ https://host/v1);
    adapter nối thêm /chat/completions.
    """

    def __init__(
        self,
        base_url: str,
        *,
        name: str = "openai_compat",
        model: str,
        api_key: str = "",
        timeout_ms: int = 120_000,
        max_retries: int = 1,
        backoff_base_s: float = 2.0,
        backoff_max_s: float = 20.0,
        max_output_tokens: int = 8192,
        temperature: float | None = None,
        headers: dict[str, str] | None = None,
        pricing: PricingConfig | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not base_url.strip():
            raise LLMError("Thiếu base_url cho adapter tương thích OpenAI", provider=name)
        if not model.strip():
            raise LLMError("Thiếu model cho adapter tương thích OpenAI", provider=name)
        self.name = name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_ms = timeout_ms
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.backoff_max_s = backoff_max_s
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.pricing = pricing or PricingConfig()
        self._api_key = api_key.strip()
        self._headers = dict(headers or {})
        self._sleep = sleep
        self._client = httpx.Client(transport=transport)

    @property
    def endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def close(self) -> None:
        self._client.close()

    def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        thinking_level: str | None = None,  # noqa: ARG002 - không có khái niệm này
        max_output_tokens: int | None = None,
        json_mode: bool = True,
        timeout_ms: int | None = None,
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "max_tokens": max_output_tokens or self.max_output_tokens,
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        timeout = (timeout_ms or self.timeout_ms) / 1000.0

        def request_once() -> LLMResponse:
            started = time.perf_counter()
            try:
                response = self._post(payload, timeout)
            except httpx.TimeoutException as exc:
                raise LLMError(
                    f"Endpoint tương thích OpenAI quá hạn sau {timeout:.0f}s",
                    provider=self.name,
                    retryable=True,
                ) from exc
            except httpx.TransportError as exc:
                raise LLMError(
                    f"Lỗi kết nối endpoint tương thích OpenAI: {type(exc).__name__}",
                    provider=self.name,
                    retryable=True,
                ) from exc
            if (
                response.status_code == 400
                and json_mode
                and "response_format" in response.text.lower()
            ):
                payload.pop("response_format", None)
                response = self._post(payload, timeout)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            if response.status_code != 200:
                raise LLMError(
                    _error_message(response),
                    provider=self.name,
                    retryable=response.status_code in RETRYABLE_STATUS,
                    status_code=response.status_code,
                )
            return self._parse_response(response.json(), elapsed_ms)

        return retry_call(
            request_once,
            max_retries=self.max_retries,
            backoff_base_s=self.backoff_base_s,
            backoff_max_s=self.backoff_max_s,
            sleep=self._sleep,
        )

    def complete_stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        thinking_level: str | None = None,  # noqa: ARG002 - không có khái niệm này
        max_output_tokens: int | None = None,
        json_mode: bool = True,
        timeout_ms: int | None = None,
    ) -> Iterator[StreamDelta]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "max_tokens": max_output_tokens or self.max_output_tokens,
            "stream": True,
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        timeout = (timeout_ms or self.timeout_ms) / 1000.0
        headers = {"content-type": "application/json", **self._headers}
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"

        started = time.perf_counter()
        collected: list[str] = []
        usage: Usage | None = None
        finish_reason: str | None = None
        model = self.model
        response_id = None
        try:
            with self._client.stream(
                "POST",
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=timeout,
            ) as response:
                if response.status_code != 200:
                    response.read()
                    raise LLMError(
                        _error_message(response),
                        provider=self.name,
                        retryable=response.status_code in RETRYABLE_STATUS,
                        status_code=response.status_code,
                    )
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        if raw == "[DONE]":
                            break
                        continue
                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(chunk, dict):
                        continue
                    model = str(chunk.get("model") or model)
                    response_id = chunk.get("id") or response_id
                    raw_usage = chunk.get("usage")
                    if isinstance(raw_usage, dict) and raw_usage:
                        usage = Usage.from_counts(
                            int(raw_usage.get("prompt_tokens") or 0),
                            int(raw_usage.get("completion_tokens") or 0),
                        )
                    for choice in chunk.get("choices") or []:
                        if not isinstance(choice, dict):
                            continue
                        delta = choice.get("delta") or {}
                        text = _content_text(delta.get("content"))
                        if text:
                            collected.append(text)
                            yield StreamDelta(text=text)
                        finish_reason = choice.get("finish_reason") or finish_reason
        except httpx.TimeoutException as exc:
            raise LLMError(
                f"Endpoint tương thích OpenAI streaming quá hạn sau {timeout:.0f}s",
                provider=self.name,
                retryable=True,
            ) from exc
        except httpx.TransportError as exc:
            raise LLMError(
                f"Lỗi kết nối endpoint tương thích OpenAI streaming: {type(exc).__name__}",
                provider=self.name,
                retryable=True,
            ) from exc

        text = "".join(collected).strip()
        if not text:
            raise LLMError(
                f"Endpoint tương thích OpenAI streaming trả về rỗng "
                f"(finish_reason={finish_reason})",
                provider=self.name,
                # Phản hồi rỗng thường do token suy luận chiếm hết hạn mức; thử lại có ích.
                retryable=True,
            )
        usage_estimated = usage is None or usage.total_tokens == 0
        if usage_estimated:
            usage = estimate_usage(messages, text)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        yield StreamDelta(
            response=LLMResponse(
                text=text,
                model=model,
                provider=self.name,
                usage=usage,
                latency_ms=elapsed_ms,
                cost_usd=self.pricing.cost_usd(usage.input_tokens, usage.output_tokens),
                finish_reason=finish_reason,
                raw={
                    "id": response_id,
                    "streamed": True,
                    "usage_estimated": usage_estimated,
                },
            ),
            done=True,
        )

    def _post(self, payload: dict, timeout: float) -> httpx.Response:
        headers = {"content-type": "application/json", **self._headers}
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"
        return self._client.post(self.endpoint, headers=headers, json=payload, timeout=timeout)

    def _parse_response(self, data: dict, elapsed_ms: float) -> LLMResponse:
        choices = data.get("choices") or []
        if not choices:
            raise LLMError(
                "Endpoint tương thích OpenAI không trả về choices",
                provider=self.name,
                retryable=False,
            )
        choice = choices[0]
        message = choice.get("message") or {}
        text = _content_text(message.get("content"))
        if not text.strip():
            raise LLMError(
                f"Endpoint tương thích OpenAI trả về rỗng "
                f"(finish_reason={choice.get('finish_reason')})",
                provider=self.name,
                # Phản hồi rỗng thường do token suy luận chiếm hết hạn mức; thử lại có ích.
                retryable=True,
            )
        raw_usage = data.get("usage") or {}
        usage = Usage.from_counts(
            int(raw_usage.get("prompt_tokens") or 0),
            int(raw_usage.get("completion_tokens") or 0),
        )
        return LLMResponse(
            text=text.strip(),
            model=str(data.get("model") or self.model),
            provider=self.name,
            usage=usage,
            latency_ms=elapsed_ms,
            cost_usd=self.pricing.cost_usd(usage.input_tokens, usage.output_tokens),
            finish_reason=choice.get("finish_reason"),
            raw={"id": data.get("id")},
        )


def _content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            str(part.get("text") or "")
            for part in content
            if isinstance(part, dict) and part.get("type") in (None, "text")
        ]
        return "".join(parts)
    return ""


def _error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
        error = data.get("error")
        message = error.get("message") if isinstance(error, dict) else str(error or "")
    except ValueError:
        message = response.text[:200]
    return f"Endpoint tương thích OpenAI trả HTTP {response.status_code}: {message[:300]}"
