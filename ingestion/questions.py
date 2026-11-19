from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .domains import resolve_question_domain
from .loaders import PdfDocument
from .normalize import clean_fragment, flatten_text, sha256_text
from .sections import Section

REFERENCE_RE = re.compile(
    r"(?i)\b(?:tài\s+liệu\s+tham\s+khảo|nguồn\s+tham\s+khảo|references?)\b\s*:?"
)
URL_RE = re.compile(r"https?://[^\s<>\"']+")
DOMAIN_LINE_RE = re.compile(r"(?im)^\s*Lĩnh\s+vực\s*:.*$")
EXPLANATION_MARKER_RE = re.compile(r"(?im)^\s*Giải\s+thích\s+tổng\s+quan\s*$")
BULLET_RE = re.compile(r"^\s*(?:[-•*]|\d+[.)])\s*(?P<text>\S.+)$")
BULLET_HEADER_HINTS = (
    "đáp án đúng",
    "đáp án chính xác",
    "câu trả lời đúng",
    "câu trả lời chính xác",
    "câu trả lời đúng đắn",
    "lựa chọn đúng",
    "lựa chọn chính xác",
    "phương án đúng",
    "phương án chính xác",
    "kỹ thuật giảm thiểu hiệu quả",
)
WRONG_HEADER_HINTS = (
    "không chính xác",
    "không đúng",
    "đều sai",
    "là sai",
)
SENTENCE_START = r"(?:^|(?<=[.!?;])\s+|(?<=:)\s+)"
OPTION_PREFIX_RE = re.compile(
    SENTENCE_START + r"(?:"
    r"Tùy chọn ghi(?: rằng)?|Tùy chọn có nội dung|Tùy chọn|"
    r"Phương án nêu|Phương án đề xuất|Phương án ghi rằng|"
    r"Thông tin cho rằng|"
    r"Các tùy chọn(?: có nội dung| sau đây)?|Các phương án(?: sau đây)?|"
    r"The option that says|The option"
    r")\s*[:\"]?\s*"
)
NEGATIVE_CUE_RE = re.compile(
    r"(?i)\s+(?:đều\s+)?(?:là\s+|is\s+)?"
    r"(?:không chính xác|không đúng|sai|incorrect|not correct)\b"
)
VIEC_WRONG_RE = re.compile(
    SENTENCE_START + r"(?P<option>Việc\s+[^.]{3,300}?)\s+là\s+"
    r"(?:không chính xác|không đúng|sai|incorrect|not correct)\b"
)
DOTTED_TOKEN_RE = re.compile(r"(?<=\w)\.(?=\w)")
PROTECTED_DOT = "․"
QUOTED_SPLIT_RE = re.compile(r"[“\"]([^”\"]{3,400})[”\"]")

ANSWER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "english_correct",
        re.compile(
            r"(?i)(?:hence|therefore|thus)[, ]+(?:the\s+)?"
            r"(?:correct|right|best)\s+(?:answer|choice|option)\s+is\s*:?\s*"
            r"(?P<answer>[^.]+)"
        ),
    ),
    (
        "english_correct",
        re.compile(
            r"(?i)(?:the\s+)?(?:correct|right|best)\s+(?:answer|choice|option)\s+"
            r"is\s*:?\s*(?P<answer>[^.]+)"
        ),
    ),
    (
        "vi_colon",
        re.compile(
            r"(?i)(?:do đó|vì vậy|vậy|như vậy|theo đó|trong trường hợp này)?"
            r"[\s,]*(?:đây là|đó là|dưới đây là)?\s*(?:các|những)?\s*"
            r"(?:câu trả lời|đáp án|phương án|giải pháp|lựa chọn|tùy chọn)"
            r"[^.!\n]{0,100}?"
            r"(?:đúng|chính xác|đúng đắn|tốt nhất|phù hợp nhất|tối ưu nhất|hiệu quả nhất)"
            r"[^.!\n]{0,40}?:\s*(?P<answer>[^.]+)"
        ),
    ),
    (
        "vi_la_correct",
        re.compile(
            r"(?i)(?P<answer>[^.!\n]{3,400}?)\s+là\s+(?:các|những)?\s*"
            r"(?:câu trả lời|đáp án|phương án|giải pháp|lựa chọn|tùy chọn)\s+"
            r"(?:đúng|chính xác|đúng đắn|tốt nhất|tốt hơn|phù hợp nhất|"
            r"tối ưu nhất|hiệu quả nhất)"
        ),
    ),
    (
        "vi_la_exact",
        re.compile(
            r"(?i)(?P<answer>[^.!\n]{3,400}?)\s+là\s+"
            r"(?:hoàn toàn\s+)?chính xác(?:\s+liên quan[^.]*)?"
        ),
    ),
    (
        "vi_solution_la",
        re.compile(
            r"(?i)(?:giải pháp|phương án|lựa chọn|tùy chọn|câu trả lời|đáp án)\s+"
            r"(?:tốt nhất|tốt hơn|phù hợp nhất|tối ưu nhất|đúng đắn|chính xác|đúng)"
            r"[^.\n]{0,40}?\s+là\s*:?\s*(?P<answer>[^.]+)"
        ),
    ),
    (
        "vi_plural_correct",
        re.compile(
            r"(?i)(?:các|những)?\s*"
            r"(?:lựa chọn|đáp án|câu trả lời|phương án|tùy chọn)"
            r"[^.\n]{0,40}(?:đúng|chính xác|đúng đắn)\s+là\s*:?\s*(?P<answer>[^.]+)"
        ),
    ),
    (
        "vi_answer_la",
        re.compile(
            r"(?i)(?:câu trả lời|đáp án|phương án|giải pháp|lựa chọn)"
            r"[^.\n]{0,60}?(?:đúng|chính xác|đúng đắn|tốt nhất|phù hợp nhất)"
            r"[^.\n]{0,20}?\s+là\s*:?\s*(?P<answer>[^.]+)"
        ),
    ),
    (
        "vi_nen",
        re.compile(
            r"(?i)(?:thay vào đó,?\s*)?(?:bạn\s+)?nên\s+"
            r"(?:sử dụng|chọn|cấu hình|triển khai|thiết lập|tạo|bật|lưu trữ|đảm bảo)\s+"
            r"(?P<answer>[^.]+)"
        ),
    ),
    (
        "vi_phai",
        re.compile(
            r"(?i)(?:thay vào đó,?\s*)?(?:bạn\s+)?phải\s+"
            r"(?:sử dụng|chọn|cấu hình|triển khai|thiết lập|tạo|bật|lưu trữ|thêm|đảm bảo)\s+"
            r"(?P<answer>[^.]+)"
        ),
    ),
    (
        "vi_chi_can",
        re.compile(
            r"(?i)(?:bạn\s+)?chỉ\s+cần\s+"
            r"(?:sử dụng|chọn|cập\s+nhật|thêm|cấu\s+hình|triển\s+khai|tạo|bật)\s+"
            r"(?P<answer>[^.]+)"
        ),
    ),
    (
        "vi_better_la",
        re.compile(r"(?i)(?:tốt\s+hơn(?:\s+hết)?|hiệu\s+quả\s+hơn)\s+là\s+" r"(?P<answer>[^.]+)"),
    ),
    (
        "vi_describe_gan_dung",
        re.compile(
            r"(?i)(?:câu\s+mô\s+tả\s+rằng|mô\s+tả\s+rằng)\s*:?\s*"
            r"(?P<answer>[^.]+?)\s+là\s+gần\s+đúng"
        ),
    ),
    (
        "vi_use_url",
        re.compile(
            r"(?i)(?:sử\s+dụng|truy\s+cập)\s+URL\s+sau\s*:\s*[•\-\s]*"
            r"(?P<answer>https?://[^\s]+)"
        ),
    ),
]

NEGATION_PREFIXES = (
    "không phải là",
    "không là",
    "chưa phải là",
    "không được xem là",
)
DISCOURSE_PREFIXES = (
    "do đó,",
    "do đó ",
    "vì vậy,",
    "vì vậy ",
    "vậy,",
    "vậy ",
    "như vậy,",
    "như vậy ",
    "theo đó,",
    "theo đó ",
    "thay vào đó,",
    "thay vào đó ",
    "trong trường hợp này,",
    "trong trường hợp này ",
    "lưu ý rằng",
    "điều này có nghĩa là",
)
VI_CHARS = set("ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ")


@dataclass
class ExtractedQuestion:
    external_id: str
    number: int
    question: str
    options: list[dict[str, Any]]
    correct_answer: str | None
    explanation: str
    domain: str
    topic: str
    source_page: int
    page_end: int
    language: str
    checksum: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "id": self.external_id,
            "external_id": self.external_id,
            "number": self.number,
            "question": self.question,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "domain": self.domain,
            "topic": self.topic,
            "source_page": self.source_page,
            "page_end": self.page_end,
            "language": self.language,
            "checksum": self.checksum,
            "metadata": self.metadata,
        }


def split_explanation(body: str) -> tuple[str, list[str]]:
    cleaned = DOMAIN_LINE_RE.sub("", body)
    cleaned = EXPLANATION_MARKER_RE.sub("", cleaned)
    match = REFERENCE_RE.search(cleaned)
    if match:
        explanation = cleaned[: match.start()].strip()
        reference_block = cleaned[match.end() :].strip()
    else:
        explanation = cleaned.strip()
        reference_block = ""
    references: list[str] = []
    for url in URL_RE.findall(reference_block):
        references.append(url.rstrip(").,;"))
    if reference_block and not references:
        for line in reference_block.split("\n"):
            item = clean_fragment(line)
            if item:
                references.append(item)
    return explanation, _dedupe(references)


def extract_correct_answer(body: str) -> tuple[str | None, str]:
    lines = [line for line in body.split("\n") if line.strip()]
    for index, line in enumerate(lines):
        if not line.rstrip().endswith(":"):
            continue
        if not _has_hint(lines, index, BULLET_HEADER_HINTS):
            continue
        bullets = _collect_bullets(lines, index)
        if bullets:
            joined = "; ".join(bullet.rstrip(" .;") for bullet in bullets)
            return joined, "bullet_list"

    flattened = DOTTED_TOKEN_RE.sub(PROTECTED_DOT, flatten_text(body))
    for source, pattern in ANSWER_PATTERNS:
        for match in pattern.finditer(flattened):
            answer = _clean_answer(match.group("answer"))
            if not answer:
                continue
            prefix = flattened[max(0, match.start() - 80) : match.start()]
            prefix = re.split(r"[.!?]\s+", prefix)[-1].lower()
            if any(negation in prefix for negation in NEGATION_PREFIXES):
                continue
            if answer.lower().startswith(NEGATION_PREFIXES):
                continue
            if answer.lower() in {"sai", "không đúng", "không chính xác"}:
                continue
            return answer.replace(PROTECTED_DOT, "."), source
    return None, "unresolved"


def _has_hint(lines: list[str], index: int, hints: tuple[str, ...], lookback: int = 3) -> bool:
    window = " ".join(lines[max(0, index - lookback) : index + 1]).lower()
    return any(hint in window for hint in hints)


def _collect_bullets(lines: list[str], header_index: int) -> list[str]:
    bullets: list[str] = []
    for line in lines[header_index + 1 :]:
        match = BULLET_RE.match(line)
        if match:
            bullets.append(clean_fragment(match.group("text")).rstrip(" .;"))
            continue
        if not bullets:
            break
        lowered = line.lower()
        if any(
            lowered.startswith(marker)
            for marker in (
                "tùy chọn",
                "phương án",
                "thông tin cho rằng",
                "việc ",
                "các tùy chọn",
                "các phương án",
                "tài liệu tham khảo",
                "lĩnh vực",
            )
        ):
            break
        if bullets[-1].endswith((".", "!", "?")):
            break
        bullets[-1] = flatten_text(f"{bullets[-1]} {line}")
    return [bullet for bullet in bullets if len(bullet) >= 3]


def _clean_answer(text: str) -> str | None:
    cleaned = clean_fragment(text)
    cleaned = re.sub(r"\*\*|__", "", cleaned)
    cleaned = cleaned.strip("\"'“”‘’`")
    lowered = cleaned.lower()
    for prefix in DISCOURSE_PREFIXES:
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip(" ,:;.-")
            lowered = cleaned.lower()
    cleaned = re.sub(r"^(?:rằng|that)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" ,:;.-")
    if len(cleaned) < 3:
        return None
    if len(cleaned) > 600:
        cleaned = cleaned[:600].rsplit(" ", 1)[0].strip()
    return cleaned


def extract_wrong_options(body: str, correct_answer: str | None) -> list[str]:
    flattened = flatten_text(body)
    options: list[str] = []
    prefixes = list(OPTION_PREFIX_RE.finditer(flattened))
    for index, match in enumerate(prefixes):
        end = prefixes[index + 1].start() if index + 1 < len(prefixes) else len(flattened)
        window = flattened[match.end() : min(end, match.end() + 800)]
        cue = NEGATIVE_CUE_RE.search(window)
        if cue is None:
            continue
        option_text = window[: cue.start()].strip()
        if ". " in option_text and not option_text.startswith(('"', "“")):
            option_text = option_text.split(". ", 1)[0]
        options.extend(_split_option_text(option_text))
    for match in VIEC_WRONG_RE.finditer(flattened):
        options.append(clean_fragment(match.group("option")))
    lines = [line for line in body.split("\n") if line.strip()]
    for index, line in enumerate(lines):
        if not line.rstrip().endswith(":"):
            continue
        if not _has_hint(lines, index, WRONG_HEADER_HINTS, lookback=6):
            continue
        window = " ".join(lines[max(0, index - 6) : index + 1]).lower()
        if "tùy chọn" not in window and "phương án" not in window:
            continue
        options.extend(_collect_bullets(lines, index))
    return _filter_wrong_options(_dedupe(options), correct_answer)


def _split_option_text(text: str) -> list[str]:
    quoted = QUOTED_SPLIT_RE.findall(text)
    if len(quoted) >= 2:
        return [clean_fragment(item) for item in quoted]
    return [clean_fragment(text)]


def _filter_wrong_options(options: list[str], correct_answer: str | None) -> list[str]:
    result: list[str] = []
    correct_lower = correct_answer.lower() if correct_answer else ""
    for option in options:
        text = re.sub(r"\*\*|__", "", option)
        text = text.replace("“", '"').replace("”", '"')
        text = text.strip("\"'‘’` ")
        if len(text) < 8 or len(text) > 500:
            continue
        lowered = text.lower()
        if lowered in {"không chính xác", "không đúng", "sai"}:
            continue
        if lowered.startswith(("việc gọi nó", "việc nói nó", "việc gọi là")):
            continue
        if correct_lower and (
            lowered == correct_lower or lowered in correct_lower or correct_lower in lowered
        ):
            continue
        if any(lowered == existing.lower() for existing in result):
            continue
        result.append(text)
    return result


def build_options(
    correct_answer: str | None, wrong_options: list[str]
) -> tuple[list[dict[str, Any]], str]:
    labels = "ABCD"
    options: list[dict[str, Any]] = []
    if correct_answer:
        options.append(
            {
                "label": labels[0],
                "text": correct_answer,
                "is_correct": True,
                "source": "reconstructed_answer",
            }
        )
        for index, wrong in enumerate(wrong_options[:3], start=1):
            options.append(
                {
                    "label": labels[index],
                    "text": wrong,
                    "is_correct": False,
                    "source": "reconstructed_distractor",
                }
            )
        return options, "reconstructed"
    for index, wrong in enumerate(wrong_options[:4]):
        options.append(
            {
                "label": labels[index],
                "text": wrong,
                "is_correct": False,
                "source": "reconstructed_distractor",
            }
        )
    return options, "reconstructed_wrong_only" if options else "unresolved"


def derive_topic(title: str) -> str:
    if ":" in title:
        head = title.split(":", 1)[0].strip()
        if 3 <= len(head) <= 120:
            return head
    return title[:120].strip()


def detect_language(text: str) -> str:
    letters = [char for char in text.lower() if char.isalpha()]
    if not letters:
        return "vi"
    vietnamese = sum(1 for char in letters if char in VI_CHARS)
    return "vi" if vietnamese / len(letters) >= 0.004 else "en"


def extract_question(section: Section, document: PdfDocument) -> ExtractedQuestion | None:
    if section.number is None:
        return None
    explanation, references = split_explanation(section.body)
    correct_answer, answer_source = extract_correct_answer(explanation)
    wrong_options = extract_wrong_options(explanation, correct_answer)
    options, options_source = build_options(correct_answer, wrong_options)
    domain, domain_source = resolve_question_domain(section.number, section.domain_raw)
    warnings: list[str] = []
    if correct_answer is None:
        warnings.append("missing_correct_answer")
    if len(wrong_options) < 3:
        warnings.append("insufficient_distractors")
    if not options:
        warnings.append("missing_options")
    external_id = f"aws-saa-q{section.number:04d}"
    topic = derive_topic(section.title)
    language = detect_language(f"{section.title} {explanation[:400]}")
    metadata = {
        "document": document.source_key,
        "document_title": document.title,
        "section_label": section.label,
        "page_end": section.page_end,
        "domain_raw": section.domain_raw,
        "domain_source": domain_source,
        "answer_source": answer_source,
        "options_source": options_source,
        "option_count": len(options),
        "wrong_options_total": len(wrong_options),
        "wrong_options_extra": wrong_options[3:],
        "references": references,
        "question_form": "topic_title",
        "warnings": warnings,
    }
    checksum = sha256_text(
        json.dumps(
            {
                "external_id": external_id,
                "question": section.title,
                "options": options,
                "correct_answer": correct_answer,
                "explanation": explanation,
                "domain": domain,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return ExtractedQuestion(
        external_id=external_id,
        number=section.number,
        question=section.title,
        options=options,
        correct_answer=correct_answer,
        explanation=explanation,
        domain=domain,
        topic=topic,
        source_page=section.page_start,
        page_end=section.page_end,
        language=language,
        checksum=checksum,
        metadata=metadata,
    )


def extract_questions(document: PdfDocument, sections: list[Section]) -> list[ExtractedQuestion]:
    questions: list[ExtractedQuestion] = []
    for section in sections:
        if section.kind != "question":
            continue
        question = extract_question(section, document)
        if question is not None:
            questions.append(question)
    questions.sort(key=lambda item: item.number)
    return questions


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
