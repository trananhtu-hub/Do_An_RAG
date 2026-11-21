"""Kiểm chứng đường ghi query_logs bằng một lượt sinh thật.

Chạy: python evaluation/verify_query_logs.py [--id GD-001]
Không in DATABASE_URL hay bất kỳ giá trị bí mật nào.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.generation.service import build_default_service  # noqa: E402
from app.services.generation.settings import load_environment  # noqa: E402
from app.services.retrieval.types import RetrievedChunk  # noqa: E402

SNAPSHOT = ROOT / "evaluation" / "results" / "gen_context_snapshot.json"
DEV_SET = ROOT / "evaluation" / "dev_generation.jsonl"


def _question(question_id: str) -> str:
    with DEV_SET.open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            if item.get("id") == question_id:
                return item["question"]
    raise SystemExit(f"Không tìm thấy {question_id}")


def _chunks(question_id: str) -> list[RetrievedChunk]:
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    return [RetrievedChunk(**item) for item in data[question_id]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default="GD-001")
    args = parser.parse_args()

    env = load_environment()
    question = _question(args.id)
    chunks = _chunks(args.id)

    service = build_default_service()
    result = service.answer(question, chunks=chunks, write_log=True)
    service.close()

    print(f"Câu hỏi: {args.id}")
    print(f"  provider: {result.provider} | model: {result.model}")
    print(f"  prompt_version: {result.prompt_version} | mode: {result.prompt_mode}")
    print(f"  tokens: {result.usage_input_tokens} vào / {result.usage_output_tokens} ra")
    print(f"  cost_usd: {result.cost_usd}")
    print(f"  latency_ms: {result.latency_ms}")
    print(f"  fallback_used: {result.fallback_used}")
    print(f"  schema_retries: {result.schema_retries}")

    import psycopg

    database_url = env.get("DATABASE_URL", "")
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select question, model, prompt_version, prompt_tokens, completion_tokens,
                       cost_usd, latency_ms, fallback_used, metadata
                from public.query_logs
                order by created_at desc
                limit 1
                """
            )
            row = cursor.fetchone()

    if row is None:
        print("query_logs: KHÔNG có dòng nào")
        return 1

    question_db, model, version, tokens_in, tokens_out, cost, latency, fallback, metadata = row
    print("query_logs (dòng mới nhất):")
    print(f"  question khớp: {question_db.strip() == question.strip()}")
    print(f"  model: {model} | prompt_version: {version}")
    print(f"  tokens: {tokens_in} vào / {tokens_out} ra")
    print(f"  cost_usd: {cost} | latency_ms: {latency} | fallback_used: {fallback}")
    print(f"  metadata.provider: {metadata.get('provider')}")
    print(f"  metadata.citation_validity: {metadata.get('citation_validity')}")
    print(f"  metadata.schema_retries: {metadata.get('schema_retries')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
