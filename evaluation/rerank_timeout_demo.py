"""Mô phỏng reranker quá thời gian chờ và kiểm tra thứ tự dự phòng RRF.

Chạy cùng một truy vấn hai lần: (1) chỉ hybrid + RRF, (2) hybrid + RRF + rerank
với timeout 1 ms để buộc fallback. Hai danh sách chunk phải trùng nhau.

Cờ --offline dùng một vector sẵn có trong DB thay cho Gemini để chạy được khi
hết quota API; phép thử fallback vẫn dùng reranker cục bộ thật.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "backend"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from app.services.retrieval.config import load_config  # noqa: E402
from app.services.retrieval.embedder import GeminiQueryEmbedder  # noqa: E402
from app.services.retrieval.rerank import CrossEncoderReranker, TimeoutReranker  # noqa: E402
from app.services.retrieval.service import RetrievalService  # noqa: E402
from app.services.retrieval.settings import load_environment  # noqa: E402
from app.services.retrieval.store import PgChunkStore  # noqa: E402

QUERY = "So sánh chi phí lưu trữ giữa S3 Standard và S3 Glacier Deep Archive"


def _config(base, overrides: dict):
    # Tắt lọc nguồn để phép so sánh chỉ đo đúng hành vi fallback của reranker.
    merged = {
        "cache": {"enabled": False},
        "classifier": {"llm_enabled": False},
        "decomposition": {"llm_enabled": False},
        "top_k": {"adaptive": False, "default": 5},
        "rerank": {"source_filter": {"enabled": False}},
    }
    for key, value in overrides.items():
        if key == "rerank":
            merged["rerank"] = {**merged["rerank"], **value}
        else:
            merged[key] = value
    return base.with_overrides(merged)


class StoredVectorEmbedder:
    """Trả lại một vector có sẵn trong DB — thay Gemini khi hết quota API."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        return [list(self._vector) for _ in texts]


def _load_stored_vector(database_url: str) -> list[float]:
    import psycopg

    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT embedding::text FROM chunks "
            "WHERE embedding IS NOT NULL AND metadata->>'kind' = 'theory' LIMIT 1"
        )
        row = cur.fetchone()
    if row is None:
        raise SystemExit("Không tìm thấy vector nào trong bảng chunks")
    return json.loads(row[0])


def _service(config, env, reranker=None, embedder=None) -> RetrievalService:
    store = PgChunkStore(env["DATABASE_URL"], ef_search=config.vector.ef_search)
    if embedder is None:
        embedder = GeminiQueryEmbedder(
            env["GEMINI_API_KEY"],
            model=config.embedding.model,
            dimensions=config.embedding.dimensions,
            task_type=config.embedding.task_type,
            timeout_ms=config.embedding.timeout_ms,
            max_retries=config.embedding.max_retries,
            cache_size=config.embedding.cache_size,
        )
    return RetrievalService(config, store, embedder, reranker=reranker, llm=None)


def _ids(result) -> list[str]:
    return [chunk.child_id for chunk in result.chunks]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="dùng vector sẵn có trong DB thay vì gọi Gemini",
    )
    args = parser.parse_args(argv)
    base = load_config(ROOT / "config/retrieval.yaml")
    env = load_environment()
    if not env.get("DATABASE_URL"):
        raise SystemExit("Thiếu DATABASE_URL trong .env")
    if not args.offline and not env.get("GEMINI_API_KEY"):
        raise SystemExit("Thiếu GEMINI_API_KEY trong .env (hoặc dùng --offline)")
    embedder = (
        StoredVectorEmbedder(_load_stored_vector(env["DATABASE_URL"])) if args.offline else None
    )
    if args.offline:
        print("Chế độ offline: vector truy vấn lấy từ bảng chunks, không gọi Gemini.\n")

    print("== 1) Hybrid + RRF, không rerank ==")
    baseline_service = _service(
        _config(base, {"rerank": {"enabled": False}}), env, embedder=embedder
    )
    try:
        baseline = baseline_service.retrieve(QUERY)
    finally:
        baseline_service.close()
    print("Thứ tự RRF:")
    for rank, chunk in enumerate(baseline.chunks, start=1):
        print(
            f"  {rank}. {chunk.child_id} [{chunk.document}] {chunk.section} "
            f"score={chunk.score:.4f}"
        )

    print("\n== 2) Hybrid + RRF + rerank với timeout 1 ms ==")
    rerank_config = _config(base, {"rerank": {"enabled": True, "timeout_ms": 1}})
    reranker = TimeoutReranker(
        CrossEncoderReranker(
            model_name=rerank_config.rerank.model,
            batch_size=rerank_config.rerank.batch_size,
            max_length=rerank_config.rerank.max_length,
            precision=rerank_config.rerank.precision,
        ),
        timeout_ms=1,
    )
    fallback_service = _service(rerank_config, env, reranker=reranker, embedder=embedder)
    started = time.perf_counter()
    try:
        fallback = fallback_service.retrieve(QUERY)
    finally:
        fallback_service.close()
    elapsed_ms = (time.perf_counter() - started) * 1000
    print("Thứ tự sau fallback:")
    for rank, chunk in enumerate(fallback.chunks, start=1):
        print(
            f"  {rank}. {chunk.child_id} [{chunk.document}] {chunk.section} "
            f"score={chunk.score:.4f}"
        )
    print(f"\nrerank_fallback = {fallback.rerank_fallback!r}")
    print(f"thời gian tầng rerank = {fallback.timings_ms.get('rerank_ms', 0):.1f} ms")
    print(f"tổng thời gian truy vấn = {elapsed_ms:.0f} ms")
    identical = _ids(baseline) == _ids(fallback)
    print(f"Thứ tự trùng với RRF: {identical}")
    if not identical:
        print(f"  RRF       : {_ids(baseline)}")
        print(f"  Fallback  : {_ids(fallback)}")
    return 0 if identical and fallback.rerank_fallback == "timeout" else 1


if __name__ == "__main__":
    raise SystemExit(main())
