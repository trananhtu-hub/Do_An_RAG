from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from .types import GenerationResult

_LOGGER = logging.getLogger(__name__)
_TABLE = re.compile(r"^[a-z_][a-z0-9_]*$")


class QueryLogWriter:
    """Ghi nhật ký sinh câu trả lời vào bảng query_logs (best effort).

    Lỗi ghi log không được làm hỏng luồng trả lời.
    """

    def __init__(
        self,
        database_url: str | None,
        *,
        enabled: bool = True,
        table: str = "query_logs",
    ) -> None:
        self.database_url = (database_url or "").strip()
        self.enabled = enabled and bool(self.database_url)
        if not _TABLE.match(table):
            raise ValueError(f"Tên bảng log không hợp lệ: {table}")
        self.table = table

    def write(
        self,
        result: GenerationResult,
        *,
        session_id: str | None = None,
        rewritten_query: str | None = None,
        user_id: str | None = None,
        ttft_ms: int | None = None,
        total_latency_ms: int | None = None,
        streaming: bool | None = None,
        status: str | None = None,
        conversation_tokens: int | None = None,
    ) -> bool:
        if not self.enabled:
            return False
        try:
            from ..sessions.pool import get_pool

            with get_pool(self.database_url).connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        insert into public.{self.table} (
                            session_id, question, rewritten_query, retrieved_chunk_ids,
                            latency_ms, prompt_tokens, completion_tokens, model,
                            metadata, prompt_version, cost_usd, fallback_used,
                            ttft_ms, total_latency_ms, streaming, user_id, status,
                            conversation_tokens
                        ) values (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            _uuid_or_none(session_id),
                            result.question,
                            rewritten_query,
                            _uuid_list(result.chunk_ids),
                            int(round(result.latency_ms)),
                            result.usage_input_tokens,
                            result.usage_output_tokens,
                            result.model,
                            json.dumps(_metadata(result), ensure_ascii=False),
                            result.prompt_version,
                            result.cost_usd,
                            result.fallback_used,
                            _int_or_none(ttft_ms if ttft_ms is not None else result.ttft_ms),
                            _int_or_none(
                                total_latency_ms
                                if total_latency_ms is not None
                                else result.latency_ms
                            ),
                            result.streaming if streaming is None else streaming,
                            _uuid_or_none(user_id),
                            status or result.status,
                            (
                                conversation_tokens
                                if conversation_tokens is not None
                                else result.conversation_tokens
                            ),
                        ),
                    )
            return True
        except Exception as exc:  # noqa: BLE001 - log không được làm hỏng luồng chính
            _LOGGER.warning("Không ghi được query_logs: %s", type(exc).__name__)
            return False


def _metadata(result: GenerationResult) -> dict[str, Any]:
    timings = result.timings_ms or {}
    return {
        "provider": result.provider,
        "judge_provider": result.extra.get("judge_provider"),
        "prompt_mode": result.prompt_mode,
        "thinking_level": result.thinking_level,
        "schema_retries": result.schema_retries,
        "attempts": list(result.attempts),
        "confidence": result.payload.confidence,
        "abstained": result.payload.abstained,
        "abstention_type": result.payload.abstention_type,
        "citation_validity": result.citation_report.citation_validity,
        "citation_warnings": [
            {"citation": issue.citation, "reason": issue.reason}
            for issue in result.citation_report.unmatched
        ],
        "warnings": list(result.warnings),
        "query_type": result.retrieval_query_type,
        "context_tokens_estimate": result.context_tokens_estimate,
        "total_tokens": result.usage_input_tokens + result.usage_output_tokens,
        "retrieval_ms": timings.get("retrieval_ms", 0.0),
        "rerank_ms": timings.get("rerank_ms", 0.0),
        "parent_expand_ms": timings.get("parent_expand_ms", 0.0),
        "prompt_ms": timings.get("prompt_ms", 0.0),
        "prefill_ms": timings.get("prefill_ms", 0.0),
        "generation_ms": timings.get("generation_ms", 0.0),
        "output_tokens": result.usage_output_tokens,
        "ttft_ms": result.ttft_ms,
        "total_ms": result.latency_ms,
        "prompt_audit": result.extra.get("prompt_audit"),
    }


def _int_or_none(value: float | int | None) -> int | None:
    if value is None:
        return None
    return int(round(value))


def _uuid_or_none(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError):
        return None


def _uuid_list(values: tuple[str, ...]) -> list[str]:
    result = []
    for value in values:
        parsed = _uuid_or_none(value)
        if parsed:
            result.append(parsed)
    return result
