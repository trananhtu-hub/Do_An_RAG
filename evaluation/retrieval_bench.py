"""Benchmark tầng truy hồi trên dev set (Giai đoạn 2).

Chấm theo mục tài liệu: một chunk được coi là liên quan nếu (tài liệu, mục)
trùng với đáp án kỳ vọng. Chỉ dùng dev set, không dùng bộ kiểm thử bên ngoài.

Cách dùng (từ thư mục gốc repo):

    python evaluation/retrieval_bench.py --config config/retrieval.yaml
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "backend"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from app.services.retrieval.config import RetrievalConfig, load_config  # noqa: E402
from app.services.retrieval.embedder import GeminiQueryEmbedder  # noqa: E402
from app.services.retrieval.service import RetrievalService  # noqa: E402
from app.services.retrieval.settings import load_environment  # noqa: E402
from app.services.retrieval.store import PgChunkStore  # noqa: E402
from app.services.retrieval.types import RetrievalResult  # noqa: E402

TARGETS = {"recall_at_5": 0.90, "mrr": 0.75, "ndcg_at_10": 0.80, "p95_ms": 1500.0}
STAGES = (
    "classify_ms",
    "decompose_ms",
    "embed_ms",
    "vector_ms",
    "lexical_ms",
    "trigram_ms",
    "fusion_ms",
    "parent_ms",
    "rerank_ms",
    "select_ms",
)
WARMUP_QUERY = "Khởi động tầng truy hồi AWS SAA"


def load_dev_set(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            for field in ("id", "query", "expected_section", "expected_document", "query_type"):
                if field not in row:
                    raise ValueError(f"Dev set thiếu trường '{field}': {line[:80]}")
            rows.append(row)
    if not rows:
        raise ValueError(f"Dev set rỗng: {path}")
    return rows


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _document_key(value: str | None) -> str:
    text = str(value or "").replace("\\", "/").strip()
    return text.rsplit("/", 1)[-1].casefold()


def _section_key(value: str | None) -> str:
    return " ".join(str(value or "").split()).casefold()


def expected_keys(row: dict[str, Any]) -> set[tuple[str, str]]:
    document = _document_key(row["expected_document"])
    sections = set(row.get("expected_sections") or [])
    sections.add(row["expected_section"])
    return {(document, _section_key(section)) for section in sections if section}


def ranked_keys(result: RetrievalResult) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    ranked: list[tuple[str, str]] = []
    for chunk in result.chunks:
        key = (_document_key(chunk.document), _section_key(chunk.section))
        if key in seen:
            continue
        seen.add(key)
        ranked.append(key)
    return ranked


def score_query(row: dict[str, Any], result: RetrievalResult) -> tuple[float, float, float]:
    relevant = expected_keys(row)
    ranked = ranked_keys(result)
    hits_at_5 = sum(1 for key in ranked[:5] if key in relevant)
    recall = min(1.0, hits_at_5 / len(relevant)) if relevant else 0.0

    mrr = 0.0
    for rank, key in enumerate(ranked, start=1):
        if key in relevant:
            mrr = 1.0 / rank
            break

    dcg = 0.0
    for rank, key in enumerate(ranked[:10], start=1):
        if key in relevant:
            dcg += 1.0 / math.log2(rank + 1)
    ideal = min(len(relevant), 10)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal + 1))
    ndcg = dcg / idcg if idcg else 0.0
    return recall, mrr, ndcg


def _profile_config(base: RetrievalConfig, profile: dict[str, Any]) -> RetrievalConfig:
    overrides = dict(profile.get("overrides") or {})
    overrides["cache"] = {**overrides.get("cache", {}), "enabled": False}
    overrides["classifier"] = {**overrides.get("classifier", {}), "llm_enabled": False}
    overrides["decomposition"] = {
        **overrides.get("decomposition", {}),
        "llm_enabled": False,
    }
    return base.with_overrides(overrides)


def _build_service(config: RetrievalConfig, env: dict[str, str]) -> RetrievalService:
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
    return RetrievalService(config, store, embedder, llm=None)


def run_profile(
    name: str,
    config: RetrievalConfig,
    dev_set: list[dict[str, Any]],
    env: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    service = _build_service(config, env)
    rows: list[dict[str, Any]] = []
    try:
        try:
            service.retrieve(WARMUP_QUERY)
        except Exception as exc:  # noqa: BLE001 - cảnh báo nhưng vẫn đo các câu thật
            print(f"  [cảnh báo] truy vấn làm nóng thất bại: {type(exc).__name__}: {exc}")
        for index, item in enumerate(dev_set, start=1):
            started = time.perf_counter()
            error = ""
            result: RetrievalResult | None = None
            try:
                result = service.retrieve(item["query"])
            except Exception as exc:  # noqa: BLE001 - ghi lỗi vào báo cáo thay vì dừng
                error = f"{type(exc).__name__}: {exc}"
            latency_ms = (time.perf_counter() - started) * 1000.0
            if result is None:
                recall = mrr = ndcg = 0.0
                timings: dict[str, float] = {stage: 0.0 for stage in STAGES}
                k = 0
            else:
                recall, mrr, ndcg = score_query(item, result)
                timings = {stage: float(result.timings_ms.get(stage, 0.0)) for stage in STAGES}
                k = result.k
            row = {
                "profile": name,
                "id": item["id"],
                "query_type": item["query_type"],
                "k": k,
                "recall_at_5": recall,
                "mrr": mrr,
                "ndcg_at_10": ndcg,
                "latency_ms": latency_ms,
                **timings,
                "cache_hit": bool(result.cache_hit) if result is not None else False,
                "rerank_fallback": (result.rerank_fallback or "") if result is not None else "",
                "error": error,
            }
            rows.append(row)
            print(
                f"  [{index:02d}/{len(dev_set)}] {item['id']} "
                f"R@5={recall:.2f} MRR={mrr:.2f} nDCG={ndcg:.2f} {latency_ms:.0f}ms"
                + (f" LỖI={error}" if error else "")
            )
    finally:
        service.close()

    latencies = [row["latency_ms"] for row in rows]
    summary: dict[str, Any] = {
        "profile": name,
        "queries": len(rows),
        "errors": sum(1 for row in rows if row["error"]),
        "recall_at_5": mean(row["recall_at_5"] for row in rows),
        "mrr": mean(row["mrr"] for row in rows),
        "ndcg_at_10": mean(row["ndcg_at_10"] for row in rows),
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "mean_ms": mean(latencies),
    }
    for stage in STAGES:
        values = [row[stage] for row in rows]
        summary[f"{stage}_p50"] = percentile(values, 0.50)
        summary[f"{stage}_p95"] = percentile(values, 0.95)
    leaf_stages = [stage for stage in STAGES if stage != "fusion_ms"]
    slowest = max(leaf_stages, key=lambda stage: summary[f"{stage}_p95"])
    summary["slowest_stage"] = slowest
    summary["slowest_p95_ms"] = summary[f"{slowest}_p95"]
    return rows, summary


def _meets_targets(summary: dict[str, Any]) -> bool:
    return (
        summary["recall_at_5"] >= TARGETS["recall_at_5"]
        and summary["mrr"] >= TARGETS["mrr"]
        and summary["ndcg_at_10"] >= TARGETS["ndcg_at_10"]
        and summary["p95_ms"] <= TARGETS["p95_ms"]
    )


def write_outputs(
    output_dir: Path,
    stamp: str,
    rows: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    dev_set_path: Path,
    profiles: list[str],
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_path = output_dir / f"retrieval_bench_{stamp}.csv"
    summary_path = output_dir / f"retrieval_bench_{stamp}_summary.csv"
    markdown_path = output_dir / f"retrieval_bench_{stamp}.md"

    detail_fields = [
        "profile",
        "id",
        "query_type",
        "k",
        "recall_at_5",
        "mrr",
        "ndcg_at_10",
        "latency_ms",
        *STAGES,
        "cache_hit",
        "rerank_fallback",
        "error",
    ]
    with detail_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=detail_fields)
        writer.writeheader()
        writer.writerows(rows)

    summary_fields = [
        "profile",
        "queries",
        "errors",
        "recall_at_5",
        "mrr",
        "ndcg_at_10",
        "p50_ms",
        "p95_ms",
        "mean_ms",
        "slowest_stage",
        "slowest_p95_ms",
    ]
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summaries)

    lines = [
        "# Benchmark truy hồi — Giai đoạn 2",
        "",
        f"- Thời điểm: {datetime.now().isoformat(timespec='seconds')}",
        f"- Dev set: `{dev_set_path}` ({summaries[0]['queries']} câu hỏi)",
        f"- Cấu hình chạy: {', '.join(profiles)}",
        "- Cách chấm: theo (tài liệu, mục); một mục đúng nằm trong top-5/top-10 là liên quan.",
        "- Mục tiêu: Recall@5 ≥ 0,90; MRR ≥ 0,75; nDCG@10 ≥ 0,80; p95 ≤ 1.500 ms.",
        "",
        "## Tổng hợp",
        "",
        "| Cấu hình | Recall@5 | MRR | nDCG@10 | p50 (ms) | p95 (ms) | "
        "Tầng chậm nhất (p95) | Đạt mục tiêu |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | :--- | :--- |",
    ]
    for summary in summaries:
        lines.append(
            "| {profile} | {recall:.3f} | {mrr:.3f} | {ndcg:.3f} | {p50:.0f} | {p95:.0f} | "
            "{slow} ({slow_p95:.0f} ms) | {target} |".format(
                profile=summary["profile"],
                recall=summary["recall_at_5"],
                mrr=summary["mrr"],
                ndcg=summary["ndcg_at_10"],
                p50=summary["p50_ms"],
                p95=summary["p95_ms"],
                slow=summary["slowest_stage"].replace("_ms", ""),
                slow_p95=summary["slowest_p95_ms"],
                target="Có" if _meets_targets(summary) else "Chưa",
            )
        )

    lines += [
        "",
        "## Theo loại câu hỏi",
        "",
        "| Cấu hình | Loại | Số câu | Recall@5 | MRR | nDCG@10 |",
        "| :--- | :--- | ---: | ---: | ---: | ---: |",
    ]
    for profile in profiles:
        profile_rows = [row for row in rows if row["profile"] == profile]
        for query_type in ("tra_cuu", "so_sanh", "nhieu_rang_buoc", "tron_thuat_ngu"):
            subset = [row for row in profile_rows if row["query_type"] == query_type]
            if not subset:
                continue
            lines.append(
                "| {profile} | {query_type} | {count} | {recall:.3f} | {mrr:.3f} | "
                "{ndcg:.3f} |".format(
                    profile=profile,
                    query_type=query_type,
                    count=len(subset),
                    recall=mean(row["recall_at_5"] for row in subset),
                    mrr=mean(row["mrr"] for row in subset),
                    ndcg=mean(row["ndcg_at_10"] for row in subset),
                )
            )

    lines += [
        "",
        "## Độ trễ từng tầng (p50 / p95, ms)",
        "",
        "| Cấu hình | " + " | ".join(stage.replace("_ms", "") for stage in STAGES) + " | total |",
        "| :--- | " + " | ".join("---:" for _ in STAGES) + " | ---: |",
    ]
    for summary in summaries:
        cells = [
            f"{summary[f'{stage}_p50']:.0f} / {summary[f'{stage}_p95']:.0f}" for stage in STAGES
        ]
        lines.append(
            f"| {summary['profile']} | "
            + " | ".join(cells)
            + f" | {summary['p50_ms']:.0f} / {summary['p95_ms']:.0f} |"
        )

    lines += [
        "",
        "## Ghi chú",
        "",
        "- `parent` là thời gian đọc nội dung chunk cha (trước rerank và/hoặc sau chọn top-k).",
        "- `select` chỉ gồm bước chọn top-k thích ứng theo ngân sách token.",
        "- `search` là thời gian lớn nhất trong ba nhánh và không cộng dồn vào tổng.",
        "- Bộ đệm truy hồi bị tắt để đo độ trễ nguội; "
        "bộ đệm embedding làm nóng một lần mỗi cấu hình.",
        "- Không dùng bộ kiểm thử bên ngoài; mọi số liệu lấy từ dev set 40 câu.",
        "",
    ]
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return detail_path, summary_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark truy hồi trên dev set")
    parser.add_argument("--config", default="config/retrieval.yaml")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument(
        "--profiles", default=None, help="Danh sách tên cấu hình, cách nhau bởi dấu phẩy"
    )
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số câu để chạy thử")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    base = load_config(config_path)

    benchmark = base.benchmark or {}
    profiles = list(benchmark.get("profiles") or [])
    if not profiles:
        raise SystemExit("Cấu hình benchmark thiếu danh sách 'profiles'")
    if args.profiles:
        wanted = {name.strip() for name in args.profiles.split(",") if name.strip()}
        profiles = [profile for profile in profiles if profile.get("name") in wanted]
        if not profiles:
            raise SystemExit("Không có cấu hình nào khớp --profiles")

    dev_set_path = Path(benchmark.get("dev_set", "evaluation/dev_set.jsonl"))
    if not dev_set_path.is_absolute():
        dev_set_path = ROOT / dev_set_path
    dev_set = load_dev_set(dev_set_path)
    if args.limit:
        dev_set = dev_set[: args.limit]

    output_dir = Path(args.output_dir or benchmark.get("output_dir", "evaluation/results"))
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    env = load_environment()
    for key in ("DATABASE_URL", "GEMINI_API_KEY"):
        if not env.get(key):
            raise SystemExit(f"Thiếu {key} trong .env")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    all_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    names: list[str] = []
    for profile in profiles:
        name = str(profile.get("name"))
        names.append(name)
        print(f"\n=== Cấu hình: {name} ===")
        config = _profile_config(base, profile)
        rows, summary = run_profile(name, config, dev_set, env)
        all_rows.extend(rows)
        summaries.append(summary)
        print(
            f"  Tổng hợp: R@5={summary['recall_at_5']:.3f} MRR={summary['mrr']:.3f} "
            f"nDCG@10={summary['ndcg_at_10']:.3f} p95={summary['p95_ms']:.0f}ms "
            f"chậm nhất={summary['slowest_stage']}"
        )

    detail_path, summary_path, markdown_path = write_outputs(
        output_dir, stamp, all_rows, summaries, dev_set_path, names
    )
    print(f"\nĐã ghi:\n  {detail_path}\n  {summary_path}\n  {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
