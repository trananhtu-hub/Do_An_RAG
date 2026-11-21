"""Xây dựng evaluation/data/dev_set.jsonl từ các đề DOCX.

Chỉ dùng thư viện chuẩn và ingestion.domains. Script không đọc/ghi kho tri thức
và không nạp bất kỳ nội dung nào vào Supabase.

Cách dùng (từ thư mục gốc repo):

    python evaluation/build_dev_set.py \
        --source evaluation/data/source \
        --output evaluation/data/dev_set.jsonl

Mỗi tệp DOCX phải có đúng 65 câu theo khuôn:
    Câu N: ...
    A. ...
    ...
    Đáp án đúng: A. ...
    Giải thích chi tiết:
    ...
    Lãnh địa (Domain): ...
    Tài liệu tham khảo:
    ...
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.domains import DOMAIN_LABELS_VI, MISSING_DOMAIN_OVERRIDES  # noqa: E402

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
QUESTION_RE = re.compile(r"^Câu\s+(\d+)\s*:\s*(.*)$")
OPTION_RE = re.compile(r"^([A-F])\.\s*(.*)$")
ANSWER_RE = re.compile(r"^Đáp án đúng:\s*(.*)$")
DOMAIN_RE = re.compile(r"^(?:Lãnh địa \(Domain\)|Lĩnh vực)\s*:\s*(.*)$")
ANSWER_LETTERS_RE = re.compile(r"^([A-F](?:\s*,\s*[A-F])*)\s*\.")
LABEL_TO_CODE = {label: code for code, label in DOMAIN_LABELS_VI.items()}
QUESTIONS_PER_EXAM = 65


def extract_paragraphs(path: Path) -> list[str]:
    """Đọc các đoạn văn bản từ word/document.xml, giữ nguyên thứ tự."""
    with zipfile.ZipFile(path) as archive:
        payload = archive.read("word/document.xml")
    root = ET.fromstring(payload)
    paragraphs: list[str] = []
    for paragraph in root.iter(WORD_NS + "p"):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == WORD_NS + "t" and node.text:
                parts.append(node.text)
            elif node.tag == WORD_NS + "tab":
                parts.append("\t")
            elif node.tag == WORD_NS + "br":
                parts.append("\n")
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def parse_answer_letters(answer_text: str) -> list[str]:
    match = ANSWER_LETTERS_RE.match(answer_text)
    if not match:
        match = re.match(r"^([A-F](?:\s*,\s*[A-F])*)", answer_text)
    if not match:
        return []
    return [letter.strip() for letter in match.group(1).split(",")]


def normalize_domain(raw: str) -> str | None:
    value = raw.strip()
    if value in LABEL_TO_CODE:
        return value
    lowered = value.lower()
    for label in DOMAIN_LABELS_VI.values():
        if label.lower() == lowered:
            return label
    if "bảo mật" in lowered or "an toàn" in lowered:
        return DOMAIN_LABELS_VI["Secure"]
    if "kiên cường" in lowered or "dự phòng" in lowered:
        return DOMAIN_LABELS_VI["Resilient"]
    if "hiệu năng" in lowered:
        return DOMAIN_LABELS_VI["High-Performing"]
    if "chi phí" in lowered:
        return DOMAIN_LABELS_VI["Cost-Optimized"]
    return None


def parse_question(
    block: list[str],
    question_no: int,
    exam_number: int,
    source_file: str,
) -> dict[str, Any]:
    question = block[0]
    options: dict[str, str] = {}
    answer_text = ""
    explanation: list[str] = []
    references: list[str] = []
    domain: str | None = None
    state = "question"
    current_option: str | None = None

    for text in block[1:]:
        if text.startswith("Giải thích chi tiết"):
            state = "explanation"
            continue
        if text.startswith("Tài liệu tham khảo"):
            state = "references"
            continue

        domain_match = DOMAIN_RE.match(text)
        if domain_match:
            domain = normalize_domain(domain_match.group(1))
            state = "domain"
            continue

        option_match = OPTION_RE.match(text)
        if option_match and state in {"question", "options"}:
            current_option = option_match.group(1)
            options[current_option] = option_match.group(2).strip()
            state = "options"
            continue

        answer_match = ANSWER_RE.match(text)
        if answer_match:
            answer_text = answer_match.group(1).strip()
            state = "answer"
            continue

        if state == "question":
            question = f"{question} {text}".strip()
        elif state == "options" and current_option is not None:
            options[current_option] = f"{options[current_option]} {text}".strip()
        elif state == "answer":
            answer_text = f"{answer_text} {text}".strip()
        elif state == "explanation":
            explanation.append(text)
        elif state == "references":
            references.append(text)

    letters = parse_answer_letters(answer_text)
    bank_question_no = (exam_number - 1) * QUESTIONS_PER_EXAM + question_no
    if domain is None:
        override_code = MISSING_DOMAIN_OVERRIDES.get(bank_question_no)
        if override_code:
            domain = DOMAIN_LABELS_VI[override_code]

    reference_options = [options[letter] for letter in letters if letter in options]
    record: dict[str, Any] = {
        "id": f"TD{exam_number}-Q{question_no:03d}",
        "exam_id": f"TD{exam_number}",
        "question_no": question_no,
        "bank_question_no": bank_question_no,
        "source_file": source_file,
        "question": question,
        "options": options,
        "answers": letters,
        "reference_answer": answer_text,
        "reference_options": reference_options,
        "question_type": "single" if len(letters) == 1 else "multiple",
        "domain": domain,
        "domain_code": LABEL_TO_CODE.get(domain) if domain else None,
        "explanation": "\n".join(explanation),
        "references": references,
        "in_knowledge_base": True,
    }
    return record


def parse_exam(path: Path, exam_number: int) -> list[dict[str, Any]]:
    paragraphs = extract_paragraphs(path)
    starts = [
        (index, int(match.group(1)), match.group(2).strip())
        for index, paragraph in enumerate(paragraphs)
        if (match := QUESTION_RE.match(paragraph))
    ]
    if not starts:
        raise RuntimeError(f"Không tìm thấy câu hỏi nào trong {path.name}")

    records: list[dict[str, Any]] = []
    for position, (start, question_no, _stem) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(paragraphs)
        block = paragraphs[start:end]
        records.append(parse_question(block, question_no, exam_number, path.name))
    return records


def infer_exam_number(path: Path, fallback: int) -> int:
    match = re.search(r"(?:de|exam|test)[-_ ]?(\d+)", path.stem, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return fallback


def validate(records: list[dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for record in records:
        record_id = record["id"]
        if record_id in seen:
            problems.append(f"Trùng id: {record_id}")
        seen.add(record_id)
        if not record["question"]:
            problems.append(f"{record_id}: thiếu nội dung câu hỏi")
        if len(record["options"]) < 2:
            problems.append(f"{record_id}: ít hơn 2 phương án")
        if not record["answers"]:
            problems.append(f"{record_id}: không đọc được đáp án")
        missing = [letter for letter in record["answers"] if letter not in record["options"]]
        if missing:
            problems.append(f"{record_id}: đáp án không có trong phương án: {missing}")
        if not record["explanation"]:
            problems.append(f"{record_id}: thiếu giải thích")
        if not record["domain"]:
            problems.append(f"{record_id}: thiếu domain")
        if record["question_no"] < 1 or record["question_no"] > QUESTIONS_PER_EXAM:
            problems.append(f"{record_id}: số câu ngoài khoảng 1-{QUESTIONS_PER_EXAM}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo dev_set.jsonl từ các đề DOCX")
    parser.add_argument("--source", type=Path, required=True, help="Tệp DOCX hoặc thư mục DOCX")
    parser.add_argument("--output", type=Path, required=True, help="Đường dẫn JSONL đầu ra")
    parser.add_argument(
        "--exam-number",
        type=int,
        default=None,
        help="Số thứ tự đề (1-6); bỏ trống để suy ra từ tên tệp",
    )
    args = parser.parse_args()

    if args.source.is_dir():
        files = sorted(args.source.glob("*.docx"), key=lambda item: item.name.lower())
    elif args.source.is_file() and args.source.suffix.lower() == ".docx":
        files = [args.source]
    else:
        raise SystemExit(f"Không tìm thấy tệp DOCX: {args.source}")

    if not files:
        raise SystemExit(f"Không có tệp DOCX trong: {args.source}")

    records: list[dict[str, Any]] = []
    for index, path in enumerate(files, start=1):
        exam_number = args.exam_number or infer_exam_number(path, index)
        exam_records = parse_exam(path, exam_number)
        if len(exam_records) != QUESTIONS_PER_EXAM:
            print(
                f"CẢNH BÁO: {path.name} có {len(exam_records)} câu, "
                f"không phải {QUESTIONS_PER_EXAM}",
                file=sys.stderr,
            )
        records.extend(exam_records)

    problems = validate(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    summary = {
        "files": [path.name for path in files],
        "questions": len(records),
        "domains": {
            domain: sum(1 for record in records if record["domain"] == domain)
            for domain in DOMAIN_LABELS_VI.values()
        },
        "multi_answer": sum(1 for record in records if record["question_type"] == "multiple"),
        "problems": problems,
        "output": str(args.output),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
