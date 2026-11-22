"""Tổng hợp kiểm toán token prompt từ kết quả ``conversation_bench``.

Đọc trường ``prompt_audit`` được đếm bằng tokenizer DeepSeek trong từng lượt, xuất
báo cáo markdown: phân bố token theo thành phần, so sánh với ``input_tokens`` do API
trả về, thống kê output và độ trễ theo lượt. Không gọi mạng.

Chạy:
    PYTHONPATH=backend;. python scripts/phase4_token_report.py \
        evaluation/results/conversation_bench_stream_20260101-000000.json
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results"

COMPONENTS = (
    "system_tokens",
    "few_shot_tokens",
    "context_tokens",
    "conversation_tokens",
    "question_tokens",
    "instruction_tokens",
    "overhead_tokens",
    "total_tokens",
)

LABELS = {
    "system_tokens": "System (không kể few-shot)",
    "few_shot_tokens": "Few-shot trong system",
    "context_tokens": "Ngữ cảnh truy xuất",
    "conversation_tokens": "Ngữ cảnh hội thoại",
    "question_tokens": "Câu hỏi",
    "instruction_tokens": "Yêu cầu đầu ra",
    "overhead_tokens": "Overhead chat (ước lượng)",
    "total_tokens": "Tổng prompt",
}


def _percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percent / 100.0 * len(ordered)) - 1))
    return ordered[index]


def _stats(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "n": len(values),
        "mean": round(sum(values) / len(values), 1),
        "p50": round(_percentile(values, 50), 1),
        "p95": round(_percentile(values, 95), 1),
        "max": round(max(values), 1),
    }


def _collect(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    turns: list[dict[str, Any]] = []
    for scenario in payload.get("results", []):
        for record in scenario.get("records", []):
            if record.get("error") or not record.get("prompt_audit"):
                continue
            turns.append(
                {
                    "source": path.name,
                    "code": scenario["code"],
                    "number": record["number"],
                    "audit": record["prompt_audit"],
                    "input_tokens": record.get("input_tokens"),
                    "output_tokens": record.get("output_tokens"),
                    "ttft_ms": record.get("ttft_ms"),
                    "latency_ms": record.get("latency_ms"),
                    "conversation_tokens": record.get("conversation_tokens"),
                    "summary_used": record.get("summary_used"),
                }
            )
    return turns


def _markdown(turns: list[dict[str, Any]], sources: list[Path]) -> str:
    exact = all(bool(turn["audit"].get("exact")) for turn in turns)
    audits = [turn["audit"] for turn in turns]
    totals = [float(audit["total_tokens"]) for audit in audits]
    api_inputs = [float(turn["input_tokens"]) for turn in turns if turn["input_tokens"]]
    outputs = [float(turn["output_tokens"]) for turn in turns if turn["output_tokens"]]
    ttfts = [float(turn["ttft_ms"]) for turn in turns if turn["ttft_ms"]]
    latencies = [float(turn["latency_ms"]) for turn in turns if turn["latency_ms"]]

    lines = [
        "# Kiểm toán token prompt (tokenizer DeepSeek)",
        "",
        f"- Thời điểm tổng hợp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- Nguồn: " + ", ".join(f"`{path.name}`" for path in sources),
        f"- Số lượt có kiểm toán: {len(turns)}",
        "- Tokenizer: "
        + ("DeepSeek (tệp tokenizer.json, chính xác)" if exact else "ước lượng ký tự/token"),
    ]
    if api_inputs:
        diff = (sum(totals) - sum(api_inputs)) / sum(api_inputs) * 100
        lines.append(
            f"- Tổng prompt theo tokenizer: {sum(totals):,.0f}; "
            f"tổng `input_tokens` API: {sum(api_inputs):,.0f}; "
            f"lệch {diff:+.1f}%"
        )
    lines += [
        "",
        "## Phân bố token theo thành phần",
        "",
        "| Thành phần | Trung bình | p50 | p95 | Lớn nhất | Tỷ lệ trung bình |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    mean_total = sum(totals) / len(totals) if totals else 0.0
    residual: list[float] = []
    for key in COMPONENTS:
        stats = _stats([float(audit.get(key, 0) or 0) for audit in audits])
        if stats is None:
            continue
        share = stats["mean"] / mean_total * 100 if mean_total else 0.0
        lines.append(
            f"| {LABELS[key]} | {stats['mean']:,.0f} | {stats['p50']:,.0f} | "
            f"{stats['p95']:,.0f} | {stats['max']:,.0f} | {share:.1f}% |"
        )
    for audit in audits:
        known = sum(int(audit.get(key, 0) or 0) for key in COMPONENTS if key != "total_tokens")
        residual.append(float(int(audit.get("total_tokens", 0) or 0) - known))
    residual_stats = _stats(residual)
    if residual_stats is not None:
        lines.append(
            f"| Khác (tiêu đề mục, phân cách) | {residual_stats['mean']:,.0f} | "
            f"{residual_stats['p50']:,.0f} | {residual_stats['p95']:,.0f} | "
            f"{residual_stats['max']:,.0f} | "
            f"{(residual_stats['mean'] / mean_total * 100) if mean_total else 0.0:.1f}% |"
        )

    if outputs:
        stats = _stats(outputs)
        assert stats is not None
        lines += [
            "",
            "## Output và độ trễ",
            "",
            f"- Output token: trung bình {stats['mean']:,.0f}, p95 {stats['p95']:,.0f}, "
            f"lớn nhất {stats['max']:,.0f}.",
        ]
    ttft_stats = _stats(ttfts)
    latency_stats = _stats(latencies)
    if ttft_stats and latency_stats:
        lines.append(
            f"- TTFT (theo lượt): p50 {ttft_stats['p50']:,.0f} ms, "
            f"p95 {ttft_stats['p95']:,.0f} ms; tổng lượt: p50 {latency_stats['p50']:,.0f} ms, "
            f"p95 {latency_stats['p95']:,.0f} ms."
        )
    lines.append("")

    max_turns = [turn for turn in turns if turn.get("number") == 4]
    if max_turns:
        conversation = [float(turn["conversation_tokens"] or 0) for turn in max_turns]
        stats = _stats(conversation)
        if stats is not None:
            lines += [
                "## Ngân sách ngữ cảnh hội thoại ở lượt 4",
                "",
                f"- Trung bình {stats['mean']:,.0f} token, p95 {stats['p95']:,.0f}, "
                f"lớn nhất {stats['max']:,.0f} (ngưỡng 1.500).",
                "",
            ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Tệp JSON kết quả conversation_bench")
    parser.add_argument("--output", default=None, help="Tệp markdown đầu ra")
    args = parser.parse_args()

    sources = [Path(item) for item in args.inputs]
    turns: list[dict[str, Any]] = []
    for path in sources:
        turns.extend(_collect(path))
    if not turns:
        raise SystemExit("Không có lượt nào kèm prompt_audit")

    report = _markdown(turns, sources)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = Path(args.output) if args.output else RESULTS / f"phase4_token_report_{stamp}.md"
    output.write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"\nĐã lưu {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
