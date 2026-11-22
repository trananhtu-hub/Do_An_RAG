"""Sinh phiếu chấm thủ công từ kết quả ``conversation_bench``.

Chọn tất định 28 lượt: lượt 1–2 của cả 10 kịch bản, cộng lượt 3–4 của hai kịch bản
đầu. Điểm judge được để ở phần cuối để người chấm không bị neo trước khi chấm.

Chạy:
    PYTHONPATH=backend;. python scripts/phase4_manual_worksheet.py \
        evaluation/results/conversation_bench_stream_20260101-000000.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results"

GRADES = ("ĐẠT", "MỘT PHẦN", "SAI")


def _select(results: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    ordered = sorted(results, key=lambda item: item["code"])
    for scenario in ordered:
        for record in scenario["records"]:
            if record["number"] in (1, 2) and not record.get("error"):
                selected.append((scenario, record))
    for scenario in ordered[:2]:
        for record in scenario["records"]:
            if record["number"] in (3, 4) and not record.get("error"):
                selected.append((scenario, record))
    return selected


def _markdown(payload: dict[str, Any], source: Path, pairs: list[tuple[dict, dict]]) -> str:
    lines = [
        "# Phiếu chấm thủ công — câu trả lời hội thoại",
        "",
        f"- Nguồn: `{source.name}` ({payload.get('transport', '?')}, "
        f"{payload.get('timestamp', '?')})",
        f"- Số lượt cần chấm: {len(pairs)}",
        "- Thang chấm: ĐẠT (trả lời đúng, đủ ý quan trọng, trích dẫn hợp lệ) / "
        "MỘT PHẦN (đúng hướng nhưng thiếu ý hoặc trích dẫn chưa chuẩn) / "
        "SAI (sai nội dung, bịa, hoặc từ chối sai).",
        '- Chấm độc lập trước khi xem phần "Đáp án máy chấm" ở cuối tệp.',
        "",
        "## Phần chấm",
        "",
    ]
    for index, (scenario, record) in enumerate(pairs, start=1):
        citations = "; ".join(
            f"{item.get('source', '')} — {item.get('quote', '')[:90]}"
            for item in record.get("citations", [])
        )
        lines += [
            f"### {index}. {scenario['code']} · lượt {record['number']}",
            "",
            f"**Hỏi:** {record['question']}",
            "",
            f"**Đáp:** {record.get('answer', '') or '(rỗng)'}",
            "",
            f"**Trích dẫn:** {citations or '(không có)'}",
            "",
            "**Chấm tay:** " + " / ".join(f"☐ {grade}" for grade in GRADES),
            "",
            "**Ghi chú:** ",
            "",
            "---",
            "",
        ]
    lines += [
        "## Đáp án máy chấm (chỉ xem sau khi chấm tay)",
        "",
        "| # | Kịch bản | Lượt | Judge | Lý do tóm tắt |",
        "| ---: | :--- | :---: | ---: | :--- |",
    ]
    for index, (scenario, record) in enumerate(pairs, start=1):
        reason = str(record.get("judge_reason", "")).replace("|", "/").replace("\n", " ")
        lines.append(
            f"| {index} | {scenario['code']} | {record['number']} | "
            f"{record.get('judge_score', 0.0):.1f} | {reason[:180]} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Tệp JSON kết quả conversation_bench")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    source = Path(args.input)
    payload = json.loads(source.read_text(encoding="utf-8"))
    pairs = _select(payload.get("results", []))
    if not pairs:
        raise SystemExit("Không có lượt nào để chấm")

    report = _markdown(payload, source, pairs)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = Path(args.output) if args.output else RESULTS / f"phase4_manual_worksheet_{stamp}.md"
    output.write_text(report + "\n", encoding="utf-8")
    print(f"Đã lưu {output} ({len(pairs)} lượt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
