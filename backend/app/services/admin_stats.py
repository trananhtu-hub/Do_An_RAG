from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from psycopg.rows import dict_row

from .sessions.pool import ConnectionPool, get_pool

_TOTALS = """
    select
        (select count(*)::int from public.questions) as questions,
        (select count(*)::int from public.documents) as documents,
        (select count(*)::int from public.chunks) as chunks,
        (select count(*)::int from public.sessions) as sessions,
        count(*)::int as queries,
        coalesce(sum(cost_usd), 0)::float8 as cost_usd,
        count(*) filter (where metadata->>'abstained' = 'true')::int as refusals,
        count(*) filter (where coalesce(status, 'complete') = 'error')::int as errors,
        percentile_cont(0.5) within group (order by total_latency_ms)::float8
            as latency_p50_ms,
        percentile_cont(0.95) within group (order by total_latency_ms)::float8
            as latency_p95_ms,
        percentile_cont(0.95) within group (order by ttft_ms)::float8 as ttft_p95_ms
    from public.query_logs
    where created_at >= now() - make_interval(days => %s)
"""

_DAILY = """
    select
        date_trunc('day', created_at) as day,
        count(*)::int as queries,
        coalesce(sum(cost_usd), 0)::float8 as cost_usd,
        count(*) filter (where metadata->>'abstained' = 'true')::int as refusals,
        percentile_cont(0.95) within group (order by total_latency_ms)::float8
            as latency_p95_ms
    from public.query_logs
    where created_at >= now() - make_interval(days => %s)
    group by 1
    order by 1
"""


class AdminStatsNotConfigured(RuntimeError):
    """Thiếu cấu hình cơ sở dữ liệu cho trang quản trị."""


class AdminStatsService:
    def __init__(self, pool: ConnectionPool | None = None) -> None:
        self._pool = pool

    def _connection_pool(self) -> ConnectionPool:
        if self._pool is not None:
            return self._pool
        try:
            return get_pool()
        except ValueError as exc:
            raise AdminStatsNotConfigured("Chưa cấu hình DATABASE_URL cho quản trị") from exc

    def stats(self, days: int = 30) -> dict[str, Any]:
        with self._connection_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(_TOTALS, (days,))
                totals = dict(cur.fetchone() or {})
                cur.execute(_DAILY, (days,))
                daily = [dict(row) for row in cur.fetchall()]
        queries = int(totals.get("queries") or 0)
        refusals = int(totals.get("refusals") or 0)
        errors = int(totals.get("errors") or 0)
        return {
            "period_days": days,
            "generated_at": datetime.now(UTC),
            "totals": {
                "questions": int(totals.get("questions") or 0),
                "documents": int(totals.get("documents") or 0),
                "chunks": int(totals.get("chunks") or 0),
                "sessions": int(totals.get("sessions") or 0),
                "queries": queries,
                "cost_usd": float(totals.get("cost_usd") or 0.0),
                "refusal_rate": round(refusals / queries, 4) if queries else 0.0,
                "error_rate": round(errors / queries, 4) if queries else 0.0,
                "latency_p50_ms": totals.get("latency_p50_ms"),
                "latency_p95_ms": totals.get("latency_p95_ms"),
                "ttft_p95_ms": totals.get("ttft_p95_ms"),
            },
            "daily": daily,
        }
