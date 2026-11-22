from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator, Sequence

import httpx

from ..config import PricingConfig
from .base import (
    LLMConfigurationError,
    LLMError,
    LLMMessage,
    LLMResponse,
    StreamDelta,
    Usage,
    estimate_usage,
    retry_call,
)

GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
STREAM_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"
)
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class GeminiAdapter:
    """Adapter Gemini 3.x.

    Gemini 3.8 Flash không nhận temperature/top_p/top_k; mức suy luận được điều
    khiển duy nhất bằng generationConfig.thinkingConfig.thinkingLevel.
    """

    def __init__(
        self,
        api_key: str | Sequence[str],
        *,
        name: str = "gemini_primary",
        model: str = "gemini-3.8-flash",
        thinking_level: str = "medium",
        timeout_ms: int = 240_000,
        max_retries: int = 1,
        backoff_base_s: float = 3.0,
        backoff_max_s: float = 30.0,
        max_output_tokens: int = 8192,
        pricing: PricingConfig | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        keys = [part.strip() for part in _as_keys(api_key) if part.strip()]
        if not keys:
            raise LLMConfigurationError("Thiếu GEMINI_API_KEY để gọi Gemini", provider=name)
        if thinking_level not in ("low", "medium", "high"):
            raise LLMConfigurationError(
                f"thinking_level không hợp lệ: {thinking_level}", provider=name
            )
        self.name = name
        self.model = model
        self.thinking_level = thinking_level
        self.timeout_ms = timeout_ms
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.backoff_max_s = backoff_max_s
        self.max_output_tokens = max_output_tokens
        self.pricing = pricing or PricingConfig()
        self._keys = list(keys)
        self._key_index = 0
        self._sleep = sleep
        self._client = httpx.Client(transport=transport)

    def close(self) -> None:
        self._client.close()

    def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        thinking_level: str | None = None,
        max_output_tokens: int | None = None,
        json_mode: bool = True,
        timeout_ms: int | None = None,
    ) -> LLMResponse:
        level = thinking_level or self.thinking_level
        if level not in ("low", "medium", "high"):
            raise LLMError(f"thinking_level không hợp lệ: {level}", provider=self.name)
        payload = self._build_payload(
            messages,
            thinking_level=level,
            max_output_tokens=max_output_tokens or self.max_output_tokens,
            json_mode=json_mode,
        )
        timeout = (timeout_ms or self.timeout_ms) / 1000.0

        def request_once() -> LLMResponse:
            started = time.perf_counter()
            try:
                response = self._client.post(
                    GENERATE_URL.format(model=self.model),
                    headers={
                        "x-goog-api-key": self._keys[self._key_index % len(self._keys)],
                        "content-type": "application/json",
                    },
                    json=payload,
                    timeout=timeout,
                )
            except httpx.TimeoutException as exc:
                raise LLMError(
                    f"Gemini quá hạn sau {timeout:.0f}s",
                    provider=self.name,
                    retryable=True,
                ) from exc
            except httpx.TransportError as exc:
                raise LLMError(
                    f"Lỗi kết nối Gemini: {type(exc).__name__}",
                    provider=self.name,
                    retryable=True,
                ) from exc
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            if response.status_code != 200:
                if response.status_code in RETRYABLE_STATUS and len(self._keys) > 1:
                    self._key_index += 1
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
        thinking_level: str | None = None,
        max_output_tokens: int | None = None,
        json_mode: bool = True,
        timeout_ms: int | None = None,
    ) -> Iterator[StreamDelta]:
        level = thinking_level or self.thinking_level
        if level not in ("low", "medium", "high"):
            raise LLMError(f"thinking_level không hợp lệ: {level}", provider=self.name)
        payload = self._build_payload(
            messages,
            thinking_level=level,
            max_output_tokens=max_output_tokens or self.max_output_tokens,
            json_mode=json_mode,
        )
        timeout = (timeout_ms or self.timeout_ms) / 1000.0
        headers = {
            "x-goog-api-key": self._keys[self._key_index % len(self._keys)],
            "content-type": "application/json",
        }
        started = time.perf_counter()
        collected: list[str] = []
        usage = Usage()
        finish_reason: str | None = None
        model = self.model
        response_id = None
        try:
            with self._client.stream(
                "POST",
                STREAM_URL.format(model=self.model),
                headers=headers,
                json=payload,
                timeout=timeout,
            ) as response:
                if response.status_code != 200:
                    response.read()
                    if response.status_code in RETRYABLE_STATUS and len(self._keys) > 1:
                        self._key_index += 1
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
                    if not raw:
                        continue
                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(chunk, dict):
                        continue
                    if chunk.get("usageMetadata"):
                        usage = _usage(chunk["usageMetadata"])
                    model = str(chunk.get("modelVersion") or model)
                    response_id = chunk.get("responseId") or response_id
                    candidates = chunk.get("candidates") or []
                    if not candidates:
                        continue
                    candidate = candidates[0]
                    finish_reason = candidate.get("finishReason") or finish_reason
                    parts = (candidate.get("content") or {}).get("parts") or []
                    for part in parts:
                        if not isinstance(part, dict) or part.get("thought"):
                            continue
                        text = part.get("text") or ""
                        if text:
                            collected.append(text)
                            yield StreamDelta(text=text)
        except httpx.TimeoutException as exc:
            raise LLMError(
                f"Gemini streaming quá hạn sau {timeout:.0f}s",
                provider=self.name,
                retryable=True,
            ) from exc
        except httpx.TransportError as exc:
            raise LLMError(
                f"Lỗi kết nối Gemini streaming: {type(exc).__name__}",
                provider=self.name,
                retryable=True,
            ) from exc

        text = "".join(collected).strip()
        if not text:
            raise LLMError(
                f"Gemini streaming trả về rỗng (finishReason={finish_reason})",
                provider=self.name,
                retryable=finish_reason in ("RECITATION", "OTHER"),
            )
        if finish_reason == "MAX_TOKENS":
            raise LLMError(
                "Gemini cắt đầu ra do MAX_TOKENS; cần tăng max_output_tokens",
                provider=self.name,
                retryable=False,
            )
        if usage.total_tokens == 0:
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
                raw={"responseId": response_id, "streamed": True},
            ),
            done=True,
        )

    def _build_payload(
        self,
        messages: Sequence[LLMMessage],
        *,
        thinking_level: str,
        max_output_tokens: int,
        json_mode: bool,
    ) -> dict[str, object]:
        system_parts = [message.content for message in messages if message.role == "system"]
        contents = [
            {
                "role": "model" if message.role == "assistant" else "user",
                "parts": [{"text": message.content}],
            }
            for message in messages
            if message.role != "system"
        ]
        generation_config: dict[str, object] = {
            "maxOutputTokens": max_output_tokens,
            "thinkingConfig": {"thinkingLevel": thinking_level},
        }
        if json_mode:
            generation_config["responseMimeType"] = "application/json"
        payload: dict[str, object] = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        return payload

    def _parse_response(self, data: dict, elapsed_ms: float) -> LLMResponse:
        feedback = data.get("promptFeedback") or {}
        block_reason = feedback.get("blockReason")
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMError(
                f"Gemini không trả về ứng viên (blockReason={block_reason})",
                provider=self.name,
                retryable=False,
            )
        candidate = candidates[0]
        finish_reason = candidate.get("finishReason")
        parts = (candidate.get("content") or {}).get("parts") or []
        texts = [
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and part.get("text") and not part.get("thought")
        ]
        text = "".join(texts).strip()
        if not text:
            raise LLMError(
                f"Gemini trả về rỗng (finishReason={finish_reason})",
                provider=self.name,
                retryable=finish_reason in ("RECITATION", "OTHER"),
            )
        if finish_reason == "MAX_TOKENS":
            raise LLMError(
                "Gemini cắt đầu ra do MAX_TOKENS; cần tăng max_output_tokens",
                provider=self.name,
                retryable=False,
            )
        usage = _usage(data.get("usageMetadata") or {})
        return LLMResponse(
            text=text,
            model=str(data.get("modelVersion") or self.model),
            provider=self.name,
            usage=usage,
            latency_ms=elapsed_ms,
            cost_usd=self.pricing.cost_usd(usage.input_tokens, usage.output_tokens),
            finish_reason=finish_reason,
            raw={"responseId": data.get("responseId")},
        )


def _as_keys(api_key: str | Sequence[str]) -> list[str]:
    source = [api_key] if isinstance(api_key, str) else list(api_key)
    keys: list[str] = []
    for item in source:
        for part in str(item).split(","):
            if part.strip():
                keys.append(part.strip())
    return keys


def _usage(raw: dict) -> Usage:
    prompt = int(raw.get("promptTokenCount") or 0)
    candidates = int(raw.get("candidatesTokenCount") or 0)
    thoughts = int(raw.get("thoughtsTokenCount") or 0)
    # Token suy luận được tính như token đầu ra khi tính chi phí.
    return Usage.from_counts(prompt, candidates + thoughts)


def _error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
        message = (data.get("error") or {}).get("message") or ""
    except ValueError:
        message = response.text[:200]
    return f"Gemini trả HTTP {response.status_code}: {message[:300]}"
