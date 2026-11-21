"""Chạy 10 truy vấn thủ công trên tầng truy hồi và in top-5 để nhận xét.

Bao phủ bốn loại: tra cứu, so sánh, nhiều ràng buộc, trộn thuật ngữ tiếng Anh.
Kết quả ghi ra Markdown trong evaluation/results/.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "backend"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from app.services.retrieval.config import load_config  # noqa: E402
from app.services.retrieval.embedder import GeminiQueryEmbedder  # noqa: E402
from app.services.retrieval.service import RetrievalService  # noqa: E402
from app.services.retrieval.settings import load_environment  # noqa: E402
from app.services.retrieval.store import PgChunkStore  # noqa: E402

MANUAL_QUERIES: list[tuple[str, str]] = [
    ("tra_cuu", "S3 Glacier Deep Archive phù hợp với những trường hợp sử dụng nào?"),
    ("tra_cuu", "VPC peering có hỗ trợ định tuyến chuyển tiếp bắc cầu giữa các VPC không?"),
    ("so_sanh", "So sánh S3 Standard-IA và S3 One Zone-IA về chi phí lưu trữ và độ bền dữ liệu."),
    ("so_sanh", "Khi nào nên chọn RDS Multi-AZ thay vì Read Replica để tăng khả năng sẵn sàng?"),
    ("so_sanh", "EBS gp3 và io2 khác nhau như thế nào về IOPS và trường hợp sử dụng?"),
    (
        "nhieu_rang_buoc",
        "Ứng dụng web ở môi trường phát triển cần độ trễ đọc thấp, chấp nhận mất một AZ "
        "và ngân sách hạn chế — nên chọn cấu hình RDS nào?",
    ),
    (
        "nhieu_rang_buoc",
        "Công ty phải lưu dữ liệu kiểm toán 7 năm, gần như không truy cập, "
        "nhưng khi kiểm toán phải truy xuất được trong vài giờ "
        "với chi phí thấp nhất — chọn lớp S3 nào?",
    ),
    (
        "nhieu_rang_buoc",
        "Hệ thống chịu tải đọc rất cao, dữ liệu ít thay đổi, cần giảm tải cho cơ sở dữ liệu chính "
        "và chấp nhận dữ liệu trễ vài giây — nên dùng giải pháp nào trên AWS?",
    ),
    ("tron_thuat_ngu", "IAM role kết hợp STS AssumeRole hoạt động thế nào khi EC2 gọi S3?"),
    (
        "tron_thuat_ngu",
        "S3 Transfer Acceleration khác gì CloudFront khi phân phối "
        "nội dung tĩnh cho người dùng toàn cầu?",
    ),
]


def _snippet(text: str, limit: int = 180) -> str:
    compact = " ".join(str(text or "").split())
    return compact[:limit] + ("…" if len(compact) > limit else "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Đánh giá thủ công top-5 cho 10 truy vấn")
    parser.add_argument("--config", default="config/retrieval.yaml")
    parser.add_argument("--profile", default="hybrid_rrf_rerank")
    parser.add_argument("--output-dir", default="evaluation/results")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    base = load_config(config_path)
    profile = next(
        (
            item
            for item in (base.benchmark or {}).get("profiles", [])
            if item.get("name") == args.profile
        ),
        None,
    )
    if profile is None:
        raise SystemExit(f"Không tìm thấy cấu hình '{args.profile}' trong benchmark.profiles")
    overrides = dict(profile.get("overrides") or {})
    overrides["cache"] = {**overrides.get("cache", {}), "enabled": False}
    overrides["classifier"] = {**overrides.get("classifier", {}), "llm_enabled": False}
    overrides["decomposition"] = {
        **overrides.get("decomposition", {}),
        "llm_enabled": False,
    }
    config = base.with_overrides(overrides)

    env = load_environment()
    for key in ("DATABASE_URL", "GEMINI_API_KEY"):
        if not env.get(key):
            raise SystemExit(f"Thiếu {key} trong .env")

    store = PgChunkStore(env["DATABASE_URL"], ef_search=config.vector.ef_search)
    embedder = GeminiQueryEmbedder(
        env["GEMINI_API_KEY"],
        model=config.embedding.model,
        dimensions=config.embedding.dimensions,
        task_type=config.embedding.task_type,
        timeout_ms=config.embedding.timeout_ms,
        max_retries=config.embedding.max_retries,
        cache_size=config.embedding.cache_size,
    )
    service = RetrievalService(config, store, embedder, llm=None)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"manual_queries_{stamp}.md"

    lines = [
        "# Đánh giá thủ công 10 truy vấn — Giai đoạn 2",
        "",
        f"- Thời điểm: {datetime.now().isoformat(timespec='seconds')}",
        f"- Cấu hình: `{args.profile}`",
        "- Mỗi truy vấn in top-5 kèm tài liệu, mục, trang và trích đoạn đầu của chunk cha.",
        "",
    ]
    try:
        service.retrieve("Khởi động tầng truy hồi")
        for index, (query_type, query) in enumerate(MANUAL_QUERIES, start=1):
            result = service.retrieve(query)
            print(f"\n[{index:02d}] ({query_type}) {query}")
            lines += [
                f"## {index}. {query}",
                "",
                f"- Loại: `{query_type}` · phân loại: `{result.query_type}` "
                f"({result.classification_source}, tin cậy {result.classification_confidence:.2f})",
                f"- k = {result.k} · độ trễ {result.timings_ms.get('total_ms', 0):.0f} ms"
                + (
                    f" · fallback rerank: `{result.rerank_fallback}`"
                    if result.rerank_fallback
                    else ""
                ),
                "",
                "| Hạng | Tài liệu | Mục | Trang | Điểm | Trích đoạn |",
                "| ---: | :--- | :--- | ---: | ---: | :--- |",
            ]
            for rank, chunk in enumerate(result.chunks, start=1):
                preview = _snippet(chunk.content)
                lines.append(
                    f"| {rank} | {chunk.document} | {chunk.section} | {chunk.page or ''} | "
                    f"{chunk.score:.3f} | {preview} |"
                )
                print(
                    f"   {rank}. [{chunk.document}] {chunk.section} tr.{chunk.page} "
                    f"score={chunk.score:.3f} — {preview[:90]}"
                )
            lines.append("")
    finally:
        service.close()

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nĐã ghi {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
