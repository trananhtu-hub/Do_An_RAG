"""Sinh bộ dev nội bộ (40 câu) từ nội dung tài liệu lý thuyết.

Mỗi câu gắn với một mục cụ thể trong kho tri thức, kèm đáp án tham chiếu và
trích dẫn nguyên văn để chấm tự động. Không dùng câu hỏi từ đề công khai.

Cách dùng:
    python evaluation/gen_dev_questions.py --limit 40 --per-call 3
    python evaluation/gen_dev_questions.py --resume
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.generation import (  # noqa: E402
    FallbackChain,
    GenerationConfig,
    LLMMessage,
    build_provider_chain,
    load_generation_config,
)
from app.services.generation.providers import LLMError  # noqa: E402
from app.services.generation.settings import load_environment  # noqa: E402

OUTPUT = ROOT / "evaluation" / "dev_generation.jsonl"
CHECKPOINT = ROOT / "evaluation" / "results" / "dev_generation_checkpoint.json"
EXCLUDED_DOCUMENTS = {"aws-saa-question-bank"}
PER_DOCUMENT = {
    "aws-saa-exam-guide": 12,
    "S3 Storage Classes": 6,
    "VPC Networking": 6,
    "RDS Aurora": 6,
    "IAM": 5,
    "EC2 Tinh toan": 5,
}

PROMPT = """Bạn là chuyên gia soạn câu hỏi ôn thi AWS SAA-C03.
Dưới đây là các mục tài liệu. Với MỖI mục, hãy tự soạn đúng MỘT câu hỏi MỚI
(không sao chép đề công khai), kèm đáp án tham chiếu ngắn gọn và 1-2 trích dẫn
nguyên văn từ nội dung mục.

Yêu cầu:
- Câu hỏi bằng tiếng Việt có dấu, giữ thuật ngữ AWS chuẩn bằng tiếng Anh.
- Đáp án tham chiếu chỉ dùng thông tin trong mục, nêu rõ dữ kiện/số liệu.
- Trích dẫn phải là chuỗi con nguyên văn của nội dung mục (tối đa 200 ký tự).
- query_type thuộc: tra_cuu, so_sanh, nhieu_rang_buoc, tron_thuat_ngu.
- cognitive_level thuộc: K1 (nhớ), K2 (hiểu), K3 (vận dụng).
- Trả JSON đúng dạng:
{{"items": [{{"document_title": "<đúng tên tài liệu>", "section": "<đúng nhãn mục>",
"question": "...", "reference_answer": "...", "quotes": ["..."],
"query_type": "tra_cuu", "cognitive_level": "K1"}}]}}
Không thêm văn bản ngoài JSON.

{blocks}
"""


@dataclass(frozen=True)
class Section:
    document_title: str
    section: str
    content: str


def section_key(item: Section | dict) -> str:
    """Khóa duy nhất theo (tài liệu, mục) — nhãn mục lặp lại giữa các tài liệu."""
    if isinstance(item, Section):
        return f"{item.document_title}||{item.section}"
    return f"{item.get('document_title') or ''}||{item.get('section') or ''}"


def load_sections() -> list[Section]:
    import psycopg

    env = load_environment()
    with psycopg.connect(env["DATABASE_URL"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select metadata->>'document_title' as title,
                       metadata->>'section' as section,
                       content
                from public.chunks
                where metadata->>'document_title' is not null
                  and parent_id is null
                order by title, section, length(content) desc
                """
            )
            rows = cursor.fetchall()
    seen: dict[tuple[str, str], Section] = {}
    for title, section, content in rows:
        if title in EXCLUDED_DOCUMENTS or not section or not content:
            continue
        key = (title, section)
        if key in seen or len(content) < 600:
            continue
        seen[key] = Section(title, section, content.strip())
    return list(seen.values())


def select_sections(sections: list[Section], limit: int, seed: int = 42) -> list[Section]:
    rng = random.Random(seed)
    by_document: dict[str, list[Section]] = {}
    for section in sections:
        by_document.setdefault(section.document_title, []).append(section)
    selected: list[Section] = []
    for title, count in PER_DOCUMENT.items():
        pool = sorted(by_document.get(title, []), key=lambda item: item.section)
        if len(pool) > count:
            selected.extend(rng.sample(pool, count))
        else:
            selected.extend(pool)
    selected.sort(key=lambda item: (item.document_title, _section_key(item.section)))
    return selected[:limit]


def _section_key(label: str) -> tuple:
    numbers = re.findall(r"\d+", label)
    return tuple(int(number) for number in numbers) or (999,)


def build_chain(config: GenerationConfig, provider: str | None) -> tuple[FallbackChain, str]:
    env = load_environment()
    if provider:
        config = config.with_overrides({"chain": [provider]})
        chain = build_provider_chain(config, environ=env)
        return chain, chain.names[0]
    chain = build_provider_chain(config, environ=env)
    return chain, chain.names[0]


def load_checkpoint() -> dict[str, dict]:
    if CHECKPOINT.exists():
        return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    return {}


def save_checkpoint(data: dict[str, dict]) -> None:
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def render_blocks(batch: list[Section]) -> str:
    parts = []
    for index, section in enumerate(batch, 1):
        parts.append(
            f"### MỤC {index}\n"
            f"Tài liệu: {section.document_title}\n"
            f"Nhãn mục: {section.section}\n"
            f"Nội dung:\n{section.content[:6000]}"
        )
    return "\n\n".join(parts)


def generate_batch(chain: FallbackChain, batch: list[Section]) -> list[dict]:
    messages = [
        LLMMessage(role="system", content="Chỉ trả về JSON hợp lệ, không thêm văn bản."),
        LLMMessage(role="user", content=PROMPT.format(blocks=render_blocks(batch))),
    ]
    response = chain.complete(messages, thinking_level="low", json_mode=True)
    data = _extract_json(response.text)
    items = data.get("items") or []
    valid: list[dict] = []
    by_section = {section_key(section): section for section in batch}
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("document_title") or "").strip()
        label = str(item.get("section") or "").strip()
        section = by_section.get(section_key({"document_title": title, "section": label}))
        if section is None:
            matches = [item_section for item_section in batch if item_section.section == label]
            if len(matches) == 1:
                section = matches[0]
        if section is None:
            continue
        answer = str(item.get("reference_answer") or "").strip()
        question = str(item.get("question") or "").strip()
        if len(question) < 15 or len(answer) < 20:
            continue
        quotes = [str(quote).strip() for quote in item.get("quotes") or []]
        content_norm = _normalize(section.content)
        quotes = [quote for quote in quotes if quote and _normalize(quote) in content_norm]
        if not quotes:
            continue
        valid.append(
            {
                "question": question,
                "reference_answer": answer,
                "document_title": section.document_title,
                "section": section.section,
                "source_quotes": quotes[:2],
                "query_type": str(item.get("query_type") or "tra_cuu"),
                "cognitive_level": str(item.get("cognitive_level") or "K1"),
                "generated_by": response.model,
            }
        )
    return valid


def _extract_json(text: str) -> dict:
    cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--per-call", type=int, default=3)
    parser.add_argument("--provider", default=None, help="gemini_primary | deepseek_fallback")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if OUTPUT.exists() and not args.force and not args.resume:
        print(f"Đã có {OUTPUT}; dùng --force để tạo lại.")
        return 0

    sections = select_sections(load_sections(), args.limit)
    print(f"{len(sections)} mục được chọn từ {len({s.document_title for s in sections})} tài liệu")
    checkpoint = load_checkpoint() if args.resume else {}
    chain, provider_name = build_chain(load_generation_config(), args.provider)
    print(f"provider: {provider_name}")

    pending = [section for section in sections if section_key(section) not in checkpoint]
    try:
        for start in range(0, len(pending), args.per_call):
            batch = pending[start : start + args.per_call]
            try:
                items = generate_batch(chain, batch)
            except LLMError as exc:
                print(f"LỖI lô {start // args.per_call + 1}: {exc}")
                continue
            for item in items:
                checkpoint[section_key(item)] = item
            save_checkpoint(checkpoint)
            done = len(checkpoint)
            print(
                f"lô {start // args.per_call + 1}: +{len(items)}/{len(batch)} " f"(tổng {done})",
                flush=True,
            )
    finally:
        chain.close()

    rows = []
    for section in sections:
        item = checkpoint.get(section_key(section))
        if not item:
            continue
        rows.append({"id": f"GD-{len(rows) + 1:03d}", **item})
    if not rows:
        print("Không sinh được câu nào.")
        return 1
    OUTPUT.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    print(f"Đã ghi {len(rows)} câu vào {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
