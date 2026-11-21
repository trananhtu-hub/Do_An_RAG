"""Kiểm tra bộ dev nội bộ trước khi dùng làm benchmark.

- Phân bố theo tài liệu, loại câu hỏi, mức nhận thức.
- Phát hiện câu trùng nhau.
- Đo trùng lặp nội dung với ngân hàng câu hỏi công khai (Jaccard token).
- Xuất báo cáo review kèm mẫu.

Cách dùng:
    python evaluation/review_dev_set.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.generation.settings import load_environment  # noqa: E402

DEV_SET = ROOT / "evaluation" / "dev_generation.jsonl"
OUTPUT = ROOT / "evaluation" / "dev_generation_review.md"
QUESTION_BANK = "aws-saa-question-bank"
_TOKEN = re.compile(r"[0-9a-zà-ỹ]+")


def tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.casefold()))


def jaccard(first: set[str], second: set[str]) -> float:
    if not first or not second:
        return 0.0
    return len(first & second) / len(first | second)


def load_dev_set() -> list[dict]:
    return [
        json.loads(line)
        for line in DEV_SET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_bank_questions() -> list[str]:
    import psycopg

    env = load_environment()
    with psycopg.connect(env["DATABASE_URL"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select content
                from public.chunks
                where metadata->>'document_title' = %s
                """,
                (QUESTION_BANK,),
            )
            return [row[0] for row in cursor.fetchall()]


def load_prior_dev_questions() -> list[str]:
    path = ROOT / "evaluation" / "dev_set.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line)["query"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    rows = load_dev_set()
    bank = load_bank_questions()
    bank_tokens = [tokens(text) for text in bank]
    prior_tokens = [tokens(text) for text in load_prior_dev_questions()]

    print(f"Tổng số câu: {len(rows)}")
    by_document = Counter(row["document_title"] for row in rows)
    by_type = Counter(row.get("query_type", "?") for row in rows)
    by_level = Counter(row.get("cognitive_level", "?") for row in rows)
    print("Theo tài liệu:", dict(by_document))
    print("Theo loại câu hỏi:", dict(by_type))
    print("Theo mức nhận thức:", dict(by_level))

    seen: dict[str, str] = {}
    duplicates = []
    for row in rows:
        key = re.sub(r"\W+", " ", row["question"].casefold()).strip()
        if key in seen:
            duplicates.append((seen[key], row["id"]))
        seen[key] = row["id"]

    overlaps = []
    prior_overlaps = []
    for row in rows:
        row_tokens = tokens(row["question"])
        best = max((jaccard(row_tokens, item) for item in bank_tokens), default=0.0)
        overlaps.append((row["id"], best))
        prior = max((jaccard(row_tokens, item) for item in prior_tokens), default=0.0)
        prior_overlaps.append((row["id"], prior))
    worst = sorted(overlaps, key=lambda item: item[1], reverse=True)[:5]
    worst_prior = sorted(prior_overlaps, key=lambda item: item[1], reverse=True)[:5]

    short_answers = [row["id"] for row in rows if len(row["reference_answer"]) < 40]
    missing_quotes = [row["id"] for row in rows if not row.get("source_quotes")]

    lines = [
        "# Review bộ dev nội bộ (Giai đoạn 3)",
        "",
        f"- Tổng số câu: **{len(rows)}**",
        f"- Câu trùng nhau: {len(duplicates)}" + (f" {duplicates}" if duplicates else ""),
        f"- Câu thiếu trích dẫn nguồn: {len(missing_quotes)}"
        + (f" {missing_quotes}" if missing_quotes else ""),
        f"- Câu có đáp án tham chiếu < 40 ký tự: {len(short_answers)}"
        + (f" {short_answers}" if short_answers else ""),
        f"- Ngân hàng câu hỏi đối chiếu: {len(bank)} chunk",
        f"- Dev set truy hồi Giai đoạn 2 đối chiếu: {len(prior_tokens)} câu",
        "",
        "## Phân bố",
        "",
        "| Tài liệu | Số câu |",
        "| :--- | ---: |",
        *[f"| {name} | {count} |" for name, count in sorted(by_document.items())],
        "",
        "| Loại câu hỏi | Số câu |",
        "| :--- | ---: |",
        *[f"| {name} | {count} |" for name, count in sorted(by_type.items())],
        "",
        "| Mức nhận thức | Số câu |",
        "| :--- | ---: |",
        *[f"| {name} | {count} |" for name, count in sorted(by_level.items())],
        "",
        "## Trùng lặp nội dung với ngân hàng câu hỏi công khai",
        "",
        "Jaccard token cao nhất của từng câu dev so với mọi chunk ngân hàng:",
        "",
        "| ID | Jaccard cao nhất |",
        "| :--- | ---: |",
        *[f"| {case_id} | {score:.3f} |" for case_id, score in worst],
        "",
        "## Trùng lặp với dev set truy hồi Giai đoạn 2",
        "",
        "| ID | Jaccard cao nhất |",
        "| :--- | ---: |",
        *[f"| {case_id} | {score:.3f} |" for case_id, score in worst_prior],
        "",
        "## Mẫu câu hỏi",
        "",
    ]
    step = max(1, len(rows) // 8)
    for row in rows[::step][:8]:
        lines.extend(
            [
                f"### {row['id']} — {row['document_title']} / {row['section']}",
                "",
                f"**Hỏi:** {row['question']}",
                "",
                f"**Đáp án tham chiếu:** {row['reference_answer']}",
                "",
                f"**Trích dẫn nguồn:** {' | '.join(row.get('source_quotes', []))}",
                "",
            ]
        )
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Đã ghi {OUTPUT}")
    print("Top trùng lặp:", worst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
