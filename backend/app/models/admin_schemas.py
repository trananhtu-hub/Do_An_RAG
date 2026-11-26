from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AdminTotals(BaseModel):
    questions: int
    documents: int
    chunks: int
    sessions: int
    queries: int
    cost_usd: float
    refusal_rate: float
    error_rate: float
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    ttft_p95_ms: float | None


class AdminDailyPoint(BaseModel):
    day: datetime
    queries: int
    cost_usd: float
    refusals: int
    latency_p95_ms: float | None


class AdminStatsResponse(BaseModel):
    period_days: int
    totals: AdminTotals
    daily: list[AdminDailyPoint]
    generated_at: datetime
